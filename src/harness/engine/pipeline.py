"""Pipeline orchestration (milestone 3, issue 3.6): the whole harness, end to end.

One issue in, one verified evidence pack out:

1. input security scan (issue 3.7) - flagged, never silently ignored
2. Architect: analyze repository -> decompose issue (issues 2.1-2.2)
3. Manager: route subtasks; disjoint file-sets run concurrently (2.4-2.6)
4. Specialists execute under the recovery ladder (2.7-2.11) with the
   budget governor metering every call (2.13)
5. Verification pipeline: self-check, tests, smells, secrets, final review
6. Evidence pack + metrics + audit trail

Spec sections intentionally absent: GitHub PR merges (no credentials at
eval time), Docker sandboxing (subprocess limits instead), web dashboard
(Textual cockpit reads the same evidence).
"""

from __future__ import annotations

import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.agents.architect import ArchitectAgent, Plan, SubTask
from harness.agents.llm_agent import StoreWindow
from harness.agents.manager import (
    ManagerAgent,
    SpecialistSlot,
    assign_specialists,
    execution_batches,
)
from harness.agents.specialists import build_agent
from harness.agents.task import Task, TaskResult
from harness.config import HarnessConfig
from harness.engine.budget import BudgetGovernor
from harness.engine.evidence import EvidencePack, build_summary
from harness.engine.recovery import Executor, RecoveryLadder, Rerouter
from harness.monitoring.metrics import MetricsCollector
from harness.security.audit import AuditLog
from harness.security.input_guard import detect_prompt_injection
from harness.tools.filesystem import summarize_repository
from harness.tools.registry import build_default_tools
from harness.verification.pipeline import VerificationPipeline, stage_report

_ROUTABLE_ERROR_TYPES = {
    "KeyError",
    "AttributeError",
    "TimeoutError",
    "ConnectionError",
    "ValueError",
    "TypeError",
}


@dataclass
class PipelineOutcome:
    run_id: str
    success: bool
    outcome_line: str
    plan: Plan | None = None
    stage_results: list[Any] = field(default_factory=list)
    task_results: list[TaskResult] = field(default_factory=list)
    evidence_path: Path | None = None
    flags: list[str] = field(default_factory=list)


class HarnessPipeline:
    """Wires every milestone-2 component into one eval-mode run."""

    def __init__(
        self,
        repo_root: Path,
        config: HarnessConfig,
        provider: Any,
        store: Any,
        audit: AuditLog | None = None,
    ) -> None:
        self._repo_root = Path(repo_root)
        self._config = config
        self._store = store
        self._audit = audit or AuditLog(self._repo_root / ".harness" / "audit.jsonl")
        self._provider = provider
        self._tools = build_default_tools(self._repo_root)
        self._agents: dict[str, Any] = {}
        self._coordination_ids: set[str] = set()
        self._manager: ManagerAgent | None = None
        self._architect: ArchitectAgent | None = None
        self._collaborators_added = 0
        # Placeholder governor: replaced per-run in `run()` before any call.
        self._placeholder_governor = BudgetGovernor(store, config.budget, "unassigned")
        self._build_agents()

    def _build_agents(self) -> None:
        slots: list[SpecialistSlot] = []
        for agent_config in self._config.agents:
            if not agent_config.enabled:
                continue
            model_config = {"provider": self._config.models["default"].provider}
            if agent_config.role == "architect":
                self._architect = ArchitectAgent(
                    agent_id=agent_config.agent_id,
                    model_config=model_config,
                    tools=self._tools,
                    context_window=StoreWindow(self._store, agent_config.agent_id, "planning"),
                    provider=self._provider,
                    store=self._store,
                    governor=self._placeholder_governor,
                )
                self._agents[agent_config.agent_id] = self._architect
                self._coordination_ids.add(agent_config.agent_id)
                continue
            if agent_config.role == "manager":
                self._manager = ManagerAgent(
                    agent_id=agent_config.agent_id,
                    model_config=model_config,
                    tools=self._tools,
                    context_window=StoreWindow(self._store, agent_config.agent_id, "coordination"),
                    provider=self._provider,
                    store=self._store,
                    governor=self._placeholder_governor,
                )
                self._agents[agent_config.agent_id] = self._manager
                self._coordination_ids.add(agent_config.agent_id)
                continue
            agent = build_agent(
                agent_id=agent_config.agent_id,
                role=agent_config.role,
                model_config=model_config,
                provider=self._provider,
                store=self._store,
                governor=self._placeholder_governor,  # replaced per-run
                tools=self._tools,
                model_tier=agent_config.model_tier,
            )
            self._agents[agent.agent_id] = agent
            from harness.agents.prompts import ROLE_PRESETS

            preset = ROLE_PRESETS.get(agent_config.role)
            specialties = set(preset.specialties) if preset else {agent_config.role}
            slots.append(
                SpecialistSlot(
                    agent_id=agent.agent_id,
                    specialties=weak_specialties(set(specialties)),
                    available_tools={tool.name for tool in self._tools},
                    model_tier=agent_config.model_tier,
                )
            )
        if self._manager is not None:
            for slot in slots:
                self._manager.register_specialist(slot)
        self._specialist_slots = slots

    async def run(self, issue_text: str, demo_mode: bool = False) -> PipelineOutcome:
        run_id = uuid.uuid4().hex[:12]
        governor = BudgetGovernor(self._store, self._config.budget, run_id)
        for agent in self._agents.values():
            agent.governor = governor
        metrics = MetricsCollector(self._store, governor)
        pack = EvidencePack(self._repo_root / self._config.run.results_dir, run_id)
        flags = [
            f"prompt-injection pattern: {pattern}"
            for pattern in detect_prompt_injection(issue_text)
        ]
        if demo_mode:
            flags.append("DEMO MODE: scripted model responses (illustrative only)")
        pack.trace(
            {"event": "run.start", "run_id": run_id, "flags": flags, "issue": issue_text[:2000]}
        )
        self._audit.append("pipeline", "run.start", run_id, {"flags": len(flags)})

        architect = self._architect
        if architect is None:
            return self._no_architect_outcome(run_id, pack)
        metrics.stage_started("architect")
        profile = await architect.analyze_repository(summarize_repository(self._repo_root))
        pack.trace(
            {"event": "architect.profile", "run_id": run_id, "profile": profile.model_dump()}
        )
        plan = await architect.decompose(issue_text, profile)
        metrics.stage_finished("architect")
        pack.trace(
            {"event": "architect.plan", "run_id": run_id, "subtasks": [s.id for s in plan.subtasks]}
        )

        task_results: list[TaskResult] = []
        metrics.stage_started("specialists")
        if self._manager is not None and plan.subtasks:
            for batch in execution_batches(plan.subtasks):
                outcomes = await self._run_batch(batch, governor, metrics, pack, run_id, architect)
                task_results.extend(outcomes)
        metrics.stage_finished("specialists")

        metrics.stage_started("verification")
        diff = self._working_diff()
        verification = VerificationPipeline(self._repo_root)
        stage_results = await verification.run(diff, plan, architect)
        metrics.stage_finished("verification")
        pack.patch(diff)
        pack.test_report(stage_report(stage_results))
        pack.token_report(metrics.report())
        overall = all(r.passed for r in stage_results if r.blocking) and all(
            r.success for r in task_results
        )
        outcome_line = (
            "VERIFIED: all tasks completed and gates passed"
            if overall
            else "NOT VERIFIED: see test-report.md and task failures"
        )
        plan_markdown = (
            "\n".join(
                f"- **{s.id}** ({s.specialty}, complexity {s.complexity}): {s.title}"
                for s in plan.subtasks
            )
            or "_no subtasks_"
        )
        pack.summary(
            build_summary(
                run_id, issue_text, plan_markdown, stage_report(stage_results), outcome_line, flags
            )
        )
        pack.trace({"event": "run.end", "run_id": run_id, "success": overall})
        self._audit.append("pipeline", "run.end", run_id, {"success": overall, "flags": len(flags)})
        return PipelineOutcome(
            run_id=run_id,
            success=overall,
            outcome_line=outcome_line,
            plan=plan,
            stage_results=stage_results,
            task_results=task_results,
            evidence_path=pack.path,
            flags=flags,
        )

    async def _run_batch(
        self,
        batch: list[SubTask],
        governor: BudgetGovernor,
        metrics: MetricsCollector,
        pack: EvidencePack,
        run_id: str,
        architect: ArchitectAgent,
    ) -> list[TaskResult]:
        """Execute one disjoint batch; specialists within it run concurrently."""
        import asyncio

        from harness.orchestration.messages import ErrorEscalation

        def make_reroute(agent_id: str) -> Rerouter:
            """Genuine L2 re-route (audit §8): 'reassign' swaps to another
            specialist; 'add collaborators' spawns one (bounded per run)."""

            def reroute(task: Task, escalation: ErrorEscalation, guidance: str) -> Executor | None:
                if "reassign" in guidance:
                    alternative = next(
                        (
                            a
                            for aid, a in self._agents.items()
                            if aid != agent_id and aid not in self._coordination_ids
                        ),
                        None,
                    )
                    return alternative.execute_task if alternative else None
                if "add collaborators" in guidance:
                    collaborator = self._add_collaborator(agent_id, governor, pack, run_id)
                    return collaborator.execute_task if collaborator else None
                return None

            return reroute

        async def run_one(subtask: SubTask) -> TaskResult:
            task = subtask.to_task()
            chosen = assign_specialists(task, self._specialist_slots, team_average_tokens=0)
            agent_id = chosen[0] if chosen else next(iter(self._agents))
            agent = self._agents[agent_id]
            pack.trace(
                {
                    "event": "specialist.assigned",
                    "run_id": run_id,
                    "task": task.id,
                    "agent": agent_id,
                }
            )
            ladder = RecoveryLadder(
                self._manager,
                architect,
                self._store,
                reroute=make_reroute(agent_id),
                on_event=pack.trace,
            )

            async def classify(t: Task, r: TaskResult) -> ErrorEscalation:
                escalation = await agent.handle_error(RuntimeError(r.error or "task failed"), t)
                # _attempt prefixes the original exception type; keep it so the
                # Manager's categorization sees KeyError/AttributeError etc.
                type_name = (r.error or "").split(":", 1)[0]
                if type_name in _ROUTABLE_ERROR_TYPES:
                    escalation = escalation.model_copy(update={"error_type": type_name})
                return escalation

            result = await ladder.run(task, agent.execute_task, classify)
            metrics.record_result(result, agent_id=agent_id)
            pack.trace(
                {
                    "event": "specialist.result",
                    "run_id": run_id,
                    "task": task.id,
                    "success": result.success,
                    "summary": result.summary[:400],
                }
            )
            return result

        return list(await asyncio.gather(*(run_one(subtask) for subtask in batch)))

    def _add_collaborator(
        self, primary_agent_id: str, governor: BudgetGovernor, pack: EvidencePack, run_id: str
    ) -> Any | None:
        """Spawn an extra specialist for a complex task (bounded, per run)."""
        if self._collaborators_added >= 2:
            return None
        self._collaborators_added += 1
        agent_id = f"{primary_agent_id}-collab-{self._collaborators_added}"
        agent = build_agent(
            agent_id=agent_id,
            role="implementer",
            model_config={"provider": self._config.models["default"].provider},
            provider=self._provider,
            store=self._store,
            governor=self._placeholder_governor,
            tools=self._tools,
        )
        agent.governor = governor
        self._agents[agent_id] = agent
        self._specialist_slots.append(
            SpecialistSlot(
                agent_id=agent_id,
                specialties=weak_specialties({"implementer"}),
                available_tools={tool.name for tool in self._tools},
            )
        )
        pack.trace(
            {
                "event": "specialist.collaborator_added",
                "run_id": run_id,
                "agent": agent_id,
                "for": primary_agent_id,
            }
        )
        return agent

    def _working_diff(self) -> str:
        try:
            proc = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=self._repo_root,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            return proc.stdout
        except (OSError, subprocess.TimeoutExpired):  # pragma: no cover - git is probed
            return ""

    def _no_architect_outcome(self, run_id: str, pack: EvidencePack) -> PipelineOutcome:
        pack.summary(
            build_summary(
                run_id,
                "(no issue)",
                "_no architect configured_",
                "no verification ran",
                "FAILED: no architect agent in configuration",
                [],
            )
        )
        return PipelineOutcome(
            run_id=run_id,
            success=False,
            outcome_line="FAILED: no architect agent in configuration",
            evidence_path=pack.path,
        )


def weak_specialties(specialties: set[str]) -> set[str]:
    """A slot covers its preset specialties plus the generic fallback."""
    return specialties | {"implementer"}
