"""Recovery ladder (milestone 2, issue 2.11 - error recovery & escalation).

Implements the unattended variant of the DESIGN_SPEC §7 hierarchy:

- L1 self-repair: retry the same specialist with its own error evidence
  (`self_repair` attempts),
- L2 manager intervention: the Manager categorizes and adds routing guidance
  (`re_route` attempts),
- L3 architect re-plan: the Architect reframes the task smaller and clearer
  (single attempt),
- L4 graceful failure: an honest `TaskResult(success=False)` - never a hang.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from harness.agents.task import Task, TaskResult
from harness.engine.budget import BudgetExhausted
from harness.infrastructure.context_store import ContextStore
from harness.infrastructure.logging import get_logger
from harness.orchestration.messages import ErrorEscalation, Severity

logger = get_logger(__name__)

Executor = Callable[[Task], Awaitable[TaskResult]]
Classifier = Callable[[Task, TaskResult], Awaitable[ErrorEscalation]]


@dataclass(frozen=True)
class AttemptPolicy:
    self_repair: int = 3
    re_route: int = 2
    re_plan: int = 1


class RecoveryLadder:
    """Drives one task through the graduated recovery levels."""

    def __init__(
        self,
        manager: Any,
        architect: Any,
        store: ContextStore,
        policy: AttemptPolicy | None = None,
    ) -> None:
        self._manager = manager
        self._architect = architect
        self._store = store
        self._policy = policy or AttemptPolicy()

    async def run(self, task: Task, executor: Executor, classify: Classifier) -> TaskResult:
        """Execute `task`, escalating through L1-L3 before giving up gracefully."""
        last_result: TaskResult | None = None
        last_escalation: ErrorEscalation | None = None

        # L1: self-repair with the agent's own error evidence
        for _ in range(self._policy.self_repair):
            last_result = await self._attempt(task, executor)
            if last_result.success:
                return last_result
            last_escalation = await classify(task, last_result)
            if last_escalation.severity == Severity.FATAL:
                return self._give_up(task, last_result, "fatal failure")

        # L2: manager intervention adds routing guidance to the task
        for _ in range(self._policy.re_route):
            guidance = await self._manager.handle_escalation(last_escalation)
            if "escalate to architect" in guidance.detail:
                break
            task = task.model_copy(
                update={
                    "metadata": {**task.metadata, "guidance": guidance.detail},
                }
            )
            last_result = await self._attempt(task, executor)
            if last_result.success:
                return last_result
            last_escalation = await classify(task, last_result)

        # L3: architect reframes the task once, smaller and clearer
        for _ in range(self._policy.re_plan):
            if last_escalation is not None:
                task = await self._architect.reframe(
                    task, f"{last_escalation.error_type}: {last_escalation.message}"
                )
            last_result = await self._attempt(task, executor)
            if last_result.success:
                return last_result
            last_escalation = await classify(task, last_result)

        return self._give_up(task, last_result, "all recovery levels exhausted")

    async def _attempt(self, task: Task, executor: Executor) -> TaskResult:
        try:
            return await executor(task)
        except BudgetExhausted:
            raise
        except Exception as exc:
            logger.warning("executor raised", task=task.id, error=str(exc)[:200])
            return TaskResult(task_id=task.id, success=False, error=str(exc)[:500])

    def _give_up(self, task: Task, result: TaskResult | None, reason: str) -> TaskResult:
        summary = result.summary if result else ""
        error = result.error if result else "unknown failure"
        logger.warning("task failed after recovery", task=task.id, reason=reason)
        return TaskResult(
            task_id=task.id,
            success=False,
            summary=summary or f"gave up: {reason}",
            error=f"{reason}: {error}",
        )
