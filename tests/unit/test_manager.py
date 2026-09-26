"""Manager tests: scoring, routing, conflicts, escalations (issues 2.4-2.6)."""

from __future__ import annotations

import pytest

from harness.agents.architect import SubTask
from harness.agents.llm_agent import StoreWindow
from harness.agents.manager import (
    ManagerAgent,
    SpecialistSlot,
    assign_specialists,
    availability,
    capability,
    categorize_escalation,
    execution_batches,
    file_overlap,
    load_balance,
    rank_specialists,
    specialty_match,
)
from harness.agents.task import Task
from harness.config import BudgetConfig
from harness.engine.budget import BudgetGovernor
from harness.infrastructure.context_store import MemoryContextStore
from harness.infrastructure.model_providers import FakeProvider, ModelResponse
from harness.orchestration.messages import CoordinationKind, ErrorEscalation, Severity


def test_specialty_match() -> None:
    assert specialty_match("testing", {"testing"}, 0.5) == 1.0
    assert specialty_match("frontend", {"testing"}, 0.9) == 0.0
    assert specialty_match(None, set(), 0.0) == 0.5  # unrouted -> neutral


def test_availability() -> None:
    assert availability(0, 2) == 1.0
    assert availability(1, 2) == 0.5
    assert availability(3, 2) == 0.0
    assert availability(1, 0) == 0.0


def test_load_balance() -> None:
    assert load_balance(50, 0) == 1.0  # no data -> neutral
    assert load_balance(50, 100) == 1.0  # under average
    assert load_balance(150, 100) == 0.5  # 50% over -> decay
    assert load_balance(300, 100) == 0.0  # clamped


def test_capability() -> None:
    assert capability(set(), set(), 4) == 1.0  # full coverage, top tier
    assert capability({"a", "b"}, {"a"}, 4) == 0.5  # half coverage
    assert capability({"a"}, {"a"}, 2) == 0.5  # coverage * tier 2/4
    assert capability(set(), set(), 1) == 0.25  # no requirements: tier still matters


def test_assignment_score_weights() -> None:
    task = Task(
        id="t",
        title="x",
        description="y",
        specialty="testing",
        complexity=5,
        required_tools=["run_tests"],
    )
    perfect = SpecialistSlot(
        "s1", specialties={"testing"}, available_tools={"run_tests"}, model_tier=4
    )
    assert assignment_score_value(task, perfect, 0) == pytest.approx(1.0)


def assignment_score_value(task: Task, slot: SpecialistSlot, team_avg: int) -> float:
    from harness.agents.manager import assignment_score

    return assignment_score(task, slot, team_avg)


def test_rank_and_route() -> None:
    task = Task(id="t", title="x", description="y", specialty="testing", complexity=5)
    tester = SpecialistSlot("tester", specialties={"testing"})
    ui = SpecialistSlot("ui-dev", specialties={"frontend"})
    ranked = rank_specialists(task, [ui, tester])
    assert ranked[0][0].agent_id == "tester"
    assert assign_specialists(task, [ui, tester]) == ["tester"]
    assert assign_specialists(task, []) == []


def test_collaboration_threshold_routes_top_three() -> None:
    task = Task(id="t", title="x", description="y", specialty="testing", complexity=9)
    slots = [SpecialistSlot(f"s{i}", specialties={"testing"}) for i in range(4)]
    chosen = assign_specialists(task, slots)
    assert len(chosen) == 3


def test_file_overlap_detects_shared_files() -> None:
    a = SubTask(id="a", title="", description="", files=["x.py", "y.py"])
    b = SubTask(id="b", title="", description="", files=["y.py"])
    c = SubTask(id="c", title="", description="", files=["z.py"])
    overlaps = file_overlap([a, b, c])
    assert overlaps == {("a", "b"): {"y.py"}}


def test_execution_batches_group_disjoint_sets() -> None:
    a = SubTask(id="a", title="", description="", files=["x.py"])
    b = SubTask(id="b", title="", description="", files=["y.py"])
    c = SubTask(id="c", title="", description="", files=["x.py"])
    batches = execution_batches([a, b, c])
    assert [[s.id for s in batch] for batch in batches] == [["a", "b"], ["c"]]


@pytest.fixture
def store() -> MemoryContextStore:
    return MemoryContextStore()


def _manager(store: MemoryContextStore, provider: FakeProvider) -> ManagerAgent:
    governor = BudgetGovernor(store, BudgetConfig(total_tokens=100_000), "corr-mgr")
    return ManagerAgent(
        agent_id="mgr-1",
        model_config={"provider": "fake"},
        tools=[],
        context_window=StoreWindow(store, "mgr-1", "coordination"),
        provider=provider,
        store=store,
        governor=governor,
    )


async def test_assign_task_routes_and_logs(store, fake_model_config) -> None:
    manager = _manager(store, FakeProvider(fake_model_config, []))
    manager.register_specialist(SpecialistSlot("impl-1", specialties={"backend-api"}))
    task = Task(id="t-1", title="x", description="y")
    await manager.assign_task(task, "impl-1")
    assert manager.assignments["t-1"] == "impl-1"
    assert manager.slots["impl-1"].current_tasks == 1
    assert store.load_global("assignments")["t-1"] == "impl-1"
    with pytest.raises(ValueError, match="unknown specialist"):
        await manager.assign_task(task, "ghost")


async def test_monitor_progress_reports_slots(store, fake_model_config) -> None:
    manager = _manager(store, FakeProvider(fake_model_config, []))
    manager.register_specialist(SpecialistSlot("busy-1", current_tasks=1, tokens_used=50))
    manager.register_specialist(SpecialistSlot("idle-1"))
    updates = await manager.monitor_progress()
    by_agent = {u.sender: u for u in updates}
    assert by_agent["busy-1"].status.value == "working"
    assert "tokens=50" in by_agent["busy-1"].detail
    assert by_agent["idle-1"].status.value == "idle"


@pytest.mark.parametrize(
    ("error_type", "message", "severity", "expected", "attempt"),
    [
        ("ToolError", "unknown tool 'nope'", Severity.RECOVERABLE, "tool_limitation", 1),
        ("ToolError", "permission denied for tool", Severity.RECOVERABLE, "tool_limitation", 1),
        ("SyntaxError", "bad output", Severity.RECOVERABLE, "unclear_requirements", 1),
        ("StructureError", "bad", Severity.RECOVERABLE, "unclear_requirements", 1),
        ("TimeoutError", "late", Severity.TRANSIENT, "transient", 1),
        ("RuntimeError", "very high complexity here", Severity.RECOVERABLE, "complex_task", 1),
        ("RuntimeError", "again", Severity.RECOVERABLE, "complex_task", 2),
        ("KeyError", "missing", Severity.RECOVERABLE, "skill_gap", 1),
        ("AttributeError", "missing", Severity.RECOVERABLE, "skill_gap", 1),
        ("WeirdError", "??? ", Severity.RECOVERABLE, "unknown", 1),
    ],
)
def test_categorize_escalation(
    error_type: str, message: str, severity: Severity, expected: str, attempt: int
) -> None:
    escalation = ErrorEscalation(
        sender="s", error_type=error_type, message=message, severity=severity, attempt=attempt
    )
    assert categorize_escalation(escalation) == expected


async def test_handle_escalation_responses(store, fake_model_config) -> None:
    manager = _manager(store, FakeProvider(fake_model_config, []))

    def esc(error_type: str, message: str, severity: Severity = Severity.RECOVERABLE):
        return ErrorEscalation(
            sender="s-1", task_id="t-1", error_type=error_type, message=message, severity=severity
        )

    assert "reassign" in (await manager.handle_escalation(esc("KeyError", "missing"))).detail
    assert (
        "tool guidance"
        in (await manager.handle_escalation(esc("ToolError", "unknown tool 'x'"))).detail
    )
    assert (
        "collaborators"
        in (await manager.handle_escalation(esc("RuntimeError", "high complexity task"))).detail
    )
    assert "reframe" in (await manager.handle_escalation(esc("SyntaxError", "bad"))).detail
    blocked = await manager.handle_escalation(esc("WeirdError", "???"))
    assert blocked.status.value == "blocked" and "architect" in blocked.detail


async def test_reframe_requirements_via_llm(store, fake_model_config) -> None:
    provider = FakeProvider(
        fake_model_config,
        responses=[
            ModelResponse(content='{"description": "add a guard clause for empty input"}'),
        ],
    )
    manager = _manager(store, provider)
    task = Task(id="t-1", title="fix", description="unclear")
    reframed = await manager.reframe_requirements(task, "what input?")
    assert reframed.description == "add a guard clause for empty input"
    assert reframed.metadata["reframed_by"] == "mgr-1"


def test_coordination_log(store, fake_model_config) -> None:
    manager = _manager(store, FakeProvider(fake_model_config, []))
    message = manager.coordination_log(CoordinationKind.TASK_ASSIGN, "impl-1", {"task": "t-1"})
    assert message.kind == CoordinationKind.TASK_ASSIGN and message.sender == "mgr-1"
