"""Milestone 4.4: recovery ladder evidence injection and genuine re-route.

Audit §8: retries must carry failure evidence, L2 guidance must reach the
task, and 'reassign'/'add collaborators' decisions may genuinely swap the
executor via the reroute callback instead of relabeling the same retry.
"""

from __future__ import annotations

from typing import Any

from harness.agents.task import Task, TaskResult
from harness.engine.recovery import AttemptPolicy, RecoveryLadder
from harness.orchestration.messages import AgentStatus, ErrorEscalation, Severity, StatusUpdate


class StubManager:
    def __init__(self, detail: str = "guidance: try a narrower edit") -> None:
        self.detail = detail
        self.escalations: list[ErrorEscalation] = []

    async def handle_escalation(self, escalation: ErrorEscalation) -> StatusUpdate:
        self.escalations.append(escalation)
        return StatusUpdate(
            sender="mgr-1",
            status=AgentStatus.WORKING,
            task_id=escalation.task_id,
            detail=self.detail,
        )


class StubArchitect:
    def __init__(self) -> None:
        self.reframed_with: str | None = None

    async def reframe(self, task: Task, failure: str) -> Task:
        self.reframed_with = failure
        return task.model_copy(update={"description": task.description + " (reframed)"})


def _escalation(
    task_id: str = "t-1", attempt: int = 1, error_type: str = "ValueError"
) -> ErrorEscalation:
    return ErrorEscalation(
        sender="impl-1",
        task_id=task_id,
        severity=Severity.RECOVERABLE,
        error_type=error_type,
        message="boom",
        attempt=attempt,
    )


class FlakyExecutor:
    """Fails N times, then succeeds; records the tasks it received."""

    def __init__(self, failures: int, task_id: str = "t-1") -> None:
        self.failures = failures
        self.task_id = task_id
        self.calls: list[Task] = []

    async def __call__(self, task: Task) -> TaskResult:
        self.calls.append(task)
        if len(self.calls) <= self.failures:
            return TaskResult(task_id=self.task_id, success=False, error="ValueError: boom")
        return TaskResult(task_id=self.task_id, success=True, summary="fixed")


async def _classify(task: Task, result: TaskResult) -> ErrorEscalation:
    return _escalation(attempt=len(result.error or ""))


async def test_l1_failure_evidence_reaches_the_retry(memory_store) -> None:
    """Retry 2's task metadata carries attempt 1's failure (audit §8)."""
    executor = FlakyExecutor(failures=1)
    events: list[dict[str, Any]] = []
    ladder = RecoveryLadder(StubManager(), StubArchitect(), memory_store, on_event=events.append)
    result = await ladder.run(Task(id="t-1", title="T", description="D"), executor, _classify)

    assert result.success
    assert len(executor.calls) == 2
    guidance = executor.calls[1].metadata["guidance"]
    assert "Previous attempt 1 failed (ValueError)" in guidance
    assert executor.calls[1].metadata["recovery"]["attempt"] == 1
    assert any(event["event"] == "recovery.l1_retry" for event in events)


async def test_l1_fatal_failure_gives_up_immediately(memory_store) -> None:
    async def classify(task: Task, result: TaskResult) -> ErrorEscalation:
        return _escalation().model_copy(update={"severity": Severity.FATAL})

    ladder = RecoveryLadder(StubManager(), StubArchitect(), memory_store)
    result = await ladder.run(
        Task(id="t-1", title="T", description="D"),
        FlakyExecutor(failures=99),
        classify,
    )
    assert not result.success
    assert "fatal failure" in (result.error or "")


async def test_l2_reassign_swaps_executor(memory_store) -> None:
    """A 'reassign' guidance genuinely switches to the replacement executor."""
    failing = FlakyExecutor(failures=99)
    replacement = FlakyExecutor(failures=0)
    reroutes: list[str] = []

    def reroute(task: Task, escalation: ErrorEscalation, guidance: str) -> Any:
        reroutes.append(guidance)
        return replacement

    ladder = RecoveryLadder(
        StubManager(detail="reassign: skill gap (KeyError)"),
        StubArchitect(),
        memory_store,
        policy=AttemptPolicy(self_repair=1, re_route=2, re_plan=1),
        reroute=reroute,
        on_event=lambda e: None,
    )
    result = await ladder.run(Task(id="t-1", title="T", description="D"), failing, _classify)
    assert result.success
    assert result.task_id == "t-1"
    assert replacement.calls and len(failing.calls) == 1  # only L1 used the original
    assert reroutes and "reassign" in reroutes[0]


async def test_l2_guidance_reaches_task_without_reroute(memory_store) -> None:
    """Without a reroute callback, guidance still lands in the task metadata."""
    executor = FlakyExecutor(failures=2)  # fails L1 + first L2 attempt
    events: list[dict[str, Any]] = []
    ladder = RecoveryLadder(
        StubManager(detail="tool guidance: use apply_edit"),
        StubArchitect(),
        memory_store,
        policy=AttemptPolicy(self_repair=1, re_route=2, re_plan=1),
        on_event=events.append,
    )
    result = await ladder.run(Task(id="t-1", title="T", description="D"), executor, _classify)

    assert result.success
    l2_attempt_task = executor.calls[2]
    assert "tool guidance" in l2_attempt_task.metadata["guidance"]
    assert any(event["event"] == "recovery.l2_guidance" for event in events)


async def test_l2_escalate_to_architect_breaks_to_l3(memory_store) -> None:
    """Manager 'escalate to architect' skips the rest of L2 for L3 reframe."""
    architect = StubArchitect()
    executor = FlakyExecutor(failures=99)
    events: list[dict[str, Any]] = []
    ladder = RecoveryLadder(
        StubManager(detail="escalate to architect"),
        architect,
        memory_store,
        policy=AttemptPolicy(self_repair=1, re_route=2, re_plan=1),
        on_event=events.append,
    )
    result = await ladder.run(Task(id="t-1", title="T", description="D"), executor, _classify)

    assert not result.success
    assert architect.reframed_with is not None
    assert "all recovery levels exhausted" in (result.error or "")
    assert any(event["event"] == "recovery.l3_replan" for event in events)
    assert not any(event["event"].startswith("recovery.l2") for event in events)


async def test_all_levels_exhausted_gives_up_gracefully(memory_store) -> None:
    ladder = RecoveryLadder(
        StubManager(detail="guidance"),
        StubArchitect(),
        memory_store,
        policy=AttemptPolicy(self_repair=2, re_route=1, re_plan=1),
    )
    result = await ladder.run(
        Task(id="t-1", title="T", description="D"), FlakyExecutor(failures=99), _classify
    )
    assert not result.success
    assert result.summary.startswith("gave up") or "exhausted" in (result.error or "")


def test_l2_loop_guards_against_empty_policy(memory_store) -> None:
    """A zero-attempt policy must not pass None escalation to the manager."""
    ladder = RecoveryLadder(
        StubManager(),
        StubArchitect(),
        memory_store,
        policy=AttemptPolicy(self_repair=0, re_route=1, re_plan=0),
    )
    result = asyncio_run_ladder(ladder)
    assert not result.success


def asyncio_run_ladder(ladder: RecoveryLadder) -> TaskResult:
    import asyncio

    async def classify(task: Task, result: TaskResult) -> ErrorEscalation:
        return _escalation().model_copy(update={"severity": Severity.FATAL})

    return asyncio.run(
        ladder.run(Task(id="t-1", title="T", description="D"), FlakyExecutor(failures=99), classify)
    )


async def test_reroute_none_keeps_same_executor(memory_store) -> None:
    """reroute returning None is legal: guidance-only retry continues."""
    executor = FlakyExecutor(failures=1)
    ladder = RecoveryLadder(
        StubManager(detail="reassign: skill gap"),
        StubArchitect(),
        memory_store,
        policy=AttemptPolicy(self_repair=1, re_route=1, re_plan=0),
        reroute=lambda task, escalation, guidance: None,
    )
    result = await ladder.run(Task(id="t-1", title="T", description="D"), executor, _classify)
    assert result.success
    assert len(executor.calls) == 2
