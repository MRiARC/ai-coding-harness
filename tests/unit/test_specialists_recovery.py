"""Specialist factory + recovery ladder tests (issues 2.8-2.11)."""

from __future__ import annotations

import pytest

from harness.agents.specialists import build_agent, roles_for_specialty
from harness.agents.task import Task, TaskResult
from harness.config import BudgetConfig
from harness.engine.budget import BudgetExhausted, BudgetGovernor
from harness.engine.recovery import AttemptPolicy, RecoveryLadder
from harness.infrastructure.context_store import MemoryContextStore
from harness.infrastructure.model_providers import FakeProvider
from harness.orchestration.messages import ErrorEscalation, Severity


def test_roles_for_specialty() -> None:
    assert roles_for_specialty("database") == ("database", "backend-api")
    assert roles_for_specialty("quantum-logic") == ("implementer",)  # fallback


def test_build_agent_applies_preset_defaults(store, fake_model_config) -> None:
    provider = FakeProvider(fake_model_config, [])
    governor = BudgetGovernor(store, BudgetConfig(total_tokens=1000), "c")
    agent = build_agent("loc-1", "locator", {"provider": "fake"}, provider, store, governor)
    assert agent.role == "locator"
    assert agent.model_tier == 2  # locator preset BASIC(1) + 1
    custom = build_agent(
        "sec-1", "security", {"provider": "fake"}, provider, store, governor, model_tier=4
    )
    assert custom.model_tier == 4
    with pytest.raises(ValueError, match="unknown role"):
        build_agent("x", "wizard", {"provider": "fake"}, provider, store, governor)


class ScriptedManager:
    """Test double for the Manager rung of the ladder."""

    def __init__(self, guidance: list[str]) -> None:
        self._guidance = list(guidance)

    async def handle_escalation(self, escalation: ErrorEscalation):
        from harness.orchestration.messages import AgentStatus, StatusUpdate

        detail = self._guidance.pop(0) if self._guidance else "keep going"
        return StatusUpdate(
            sender="mgr", status=AgentStatus.WORKING, task_id=escalation.task_id, detail=detail
        )


class ScriptedArchitect:
    """Test double for the Architect rung of the ladder."""

    def __init__(self) -> None:
        self.reframe_calls = 0

    async def reframe(self, task: Task, escalation_message: str) -> Task:
        self.reframe_calls += 1
        return task.model_copy(
            update={
                "description": f"{task.description} [reframed: {escalation_message[:40]}]",
                "metadata": {**task.metadata, "reframed": True},
            }
        )


def _ladder(store: MemoryContextStore, guidance: list[str]) -> RecoveryLadder:
    return RecoveryLadder(ScriptedManager(guidance), ScriptedArchitect(), store)


async def _classify(_task: Task, result) -> ErrorEscalation:
    return ErrorEscalation(
        sender="x",
        task_id=result.task_id,
        severity=Severity.RECOVERABLE,
        error_type="RuntimeError",
        message=result.error or "unknown",
    )


async def test_success_on_first_attempt(store) -> None:
    calls = {"n": 0}

    async def executor(task: Task):
        calls["n"] += 1
        return TaskResult(task_id=task.id, success=True, summary="done")

    result = await _ladder(store, []).run(
        Task(id="t", title="", description=""), executor, _classify
    )
    assert result.success and calls["n"] == 1


async def test_l1_transient_retries_then_success(store) -> None:
    calls = {"n": 0}

    async def executor(task: Task):
        calls["n"] += 1
        if calls["n"] < 3:
            return TaskResult(task_id=task.id, success=False, error="flaky")
        return TaskResult(task_id=task.id, success=True, summary="recovered")

    result = await _ladder(store, []).run(
        Task(id="t", title="", description=""), executor, _classify
    )
    assert result.success and calls["n"] == 3


async def test_fatal_stops_immediately(store) -> None:
    async def executor(task: Task):
        return TaskResult(task_id=task.id, success=False, error="hopeless")

    async def fatal(_task, result):
        return ErrorEscalation(
            sender="x",
            task_id=result.task_id,
            severity=Severity.FATAL,
            error_type="BudgetExhausted",
            message="spent",
        )

    result = await _ladder(store, []).run(Task(id="t", title="", description=""), executor, fatal)
    assert not result.success and "fatal failure" in result.error


async def test_l2_guidance_helps(store) -> None:
    state = {"n": 0}

    async def executor(task: Task):
        state["n"] += 1
        if "narrower" not in task.metadata.get("guidance", ""):
            return TaskResult(task_id=task.id, success=False, error="too broad")
        return TaskResult(task_id=task.id, success=True, summary="with guidance")

    ladder = _ladder(store, guidance=["try narrower scope"])
    result = await ladder.run(Task(id="t", title="", description=""), executor, _classify)
    assert result.success and state["n"] == 4  # 3 x L1 + 1 guided L2 attempt


async def test_l2_escalate_to_architect_jump(store) -> None:
    """Manager says 'escalate to architect' -> ladder skips remaining L2 attempts."""
    state = {"n": 0}

    async def executor(task: Task):
        state["n"] += 1
        return TaskResult(task_id=task.id, success=False, error="stuck")

    ladder = _ladder(store, guidance=["escalate to architect"])
    result = await ladder.run(Task(id="t", title="", description=""), executor, _classify)
    assert not result.success
    assert state["n"] == 3 + 1  # L1 budget + single L2 attempt that escalated


async def test_l3_reframe_succeeds(store) -> None:
    architect = ScriptedArchitect()
    state = {"n": 0}

    async def executor(task: Task):
        state["n"] += 1
        if task.metadata.get("reframed"):
            return TaskResult(task_id=task.id, success=True, summary="clear now")
        return TaskResult(task_id=task.id, success=False, error="confused")

    ladder = RecoveryLadder(ScriptedManager(["escalate to architect"]), architect, store)
    result = await ladder.run(Task(id="t", title="", description=""), executor, _classify)
    assert result.success and architect.reframe_calls == 1


async def test_all_levels_exhausted_gives_up_gracefully(store) -> None:
    async def executor(task: Task):
        return TaskResult(task_id=task.id, success=False, error="never works")

    result = await _ladder(store, guidance=["try", "try again"]).run(
        Task(id="t", title="", description=""), executor, _classify
    )
    assert not result.success
    assert "all recovery levels exhausted" in result.error
    assert "never works" in result.error


async def test_executor_crash_becomes_failed_attempt(store) -> None:
    calls = {"n": 0}

    async def executor(task: Task):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("exploded")
        return TaskResult(task_id=task.id, success=True, summary="second try")

    result = await _ladder(store, []).run(
        Task(id="t", title="", description=""), executor, _classify
    )
    assert result.success and calls["n"] == 2


async def test_budget_exhaustion_propagates(store) -> None:
    async def executor(task: Task):
        raise BudgetExhausted("spent")

    with pytest.raises(BudgetExhausted):
        await _ladder(store, []).run(Task(id="t", title="", description=""), executor, _classify)


def test_attempt_policy_defaults() -> None:
    policy = AttemptPolicy()
    assert (policy.self_repair, policy.re_route, policy.re_plan) == (3, 2, 1)
