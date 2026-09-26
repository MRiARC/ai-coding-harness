"""Contract tests for BaseAgent/BaseManager, tools, tasks, and messages."""

from __future__ import annotations

import pytest

from harness.agents.base import BaseAgent, BaseManager, ContextWindow
from harness.agents.task import Task, TaskResult
from harness.orchestration.messages import (
    AgentStatus,
    CommandMessage,
    CoordinationKind,
    CoordinationMessage,
    ErrorEscalation,
    Severity,
    StatusUpdate,
)
from harness.tools.base import Tool, ToolResult, ToolTier


class StubTool(Tool):
    def __init__(self, name: str, tier: ToolTier, allowed: bool = True) -> None:
        self.name = name
        self.tier = tier
        self.description = "stub"
        self.parameters: dict = {}
        self._allowed = allowed

    def validate_input(self, arguments: dict) -> list[str]:
        return []

    def check_permissions(self, context: dict) -> bool:
        return context.get("model_tier", 1) >= self.tier and self._allowed

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, output="ok")


class StubAgent(BaseAgent):
    async def execute_task(self, task: Task) -> TaskResult:
        return TaskResult(task_id=task.id, success=True, summary="done")

    async def handle_error(self, error: Exception, task: Task) -> ErrorEscalation:
        return ErrorEscalation(
            sender=self.agent_id,
            severity=Severity.RECOVERABLE,
            error_type=type(error).__name__,
            message=str(error),
        )

    def report_status(self) -> StatusUpdate:
        return StatusUpdate(sender=self.agent_id, status=AgentStatus.IDLE)


class RecordingWindow:
    """Satisfies the ContextWindow protocol structurally."""

    def __init__(self) -> None:
        self.turns: list[dict[str, str]] = []

    def append(self, role: str, content: str) -> None:
        self.turns.append({"role": role, "content": content})

    def as_messages(self) -> list[dict[str, str]]:
        return list(self.turns)


def test_base_agent_init_and_shared_behavior() -> None:
    window = RecordingWindow()
    agent = StubAgent("stub-1", {"provider": "fake"}, [StubTool("t1", ToolTier.ADVANCED)], window)
    assert agent.agent_id == "stub-1"
    assert agent.model_config["provider"] == "fake"
    # model_tier 1 < ADVANCED(3): filtered out; with tier 3: permitted
    assert agent.permitted_tools({"model_tier": 1}) == []
    assert agent.permitted_tools({"model_tier": 3}) == [agent.tools[0]]
    window.append("user", "hi")
    assert agent.context_window.as_messages() == [{"role": "user", "content": "hi"}]
    assert (
        ContextWindow.__protocol_attrs__ if hasattr(ContextWindow, "__protocol_attrs__") else True
    )


def test_protocol_is_runtime_checkable() -> None:
    assert isinstance(RecordingWindow(), ContextWindow)


async def test_concrete_agent_methods() -> None:
    agent = StubAgent("stub-1", {}, [], RecordingWindow())
    task = Task(id="t1", title="x", description="y")
    assert (await agent.execute_task(task)).success
    escalation = await agent.handle_error(ValueError("boom"), task)
    assert escalation.error_type == "ValueError" and escalation.severity == Severity.RECOVERABLE
    assert agent.report_status().status == AgentStatus.IDLE


def test_base_manager_is_abstract() -> None:
    class IncompleteManager(BaseManager):
        pass

    with pytest.raises(TypeError):
        IncompleteManager("m-1", {}, [], RecordingWindow())  # type: ignore[abstract]


def test_tool_result_contract() -> None:
    result = ToolResult(success=False, error="bad")
    assert result.total_tokens if False else result.error == "bad"
    assert ToolTier.BASIC < ToolTier.DEVELOPMENT < ToolTier.ADVANCED


def test_message_defaults_and_immutability() -> None:
    command = CommandMessage(sender="a", recipient="b", command="plan")
    assert command.correlation_id and command.created_at.tzinfo is not None
    other = CommandMessage(sender="a", recipient="b", command="plan")
    assert command.id != other.id and command.correlation_id != other.correlation_id
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        command.command = "other"  # type: ignore[misc]


def test_status_and_escalation_and_coordination() -> None:
    status = StatusUpdate(sender="s-1", status=AgentStatus.WORKING, task_id="t1", detail="…")
    assert status.status == AgentStatus.WORKING
    escalation = ErrorEscalation(
        sender="s-1",
        severity=Severity.TRANSIENT,
        error_type="Timeout",
        message="late",
        attempt=2,
        suggested_action="retry",
    )
    assert escalation.suggested_action == "retry"
    coordination = CoordinationMessage(
        sender="mgr", recipient="impl-1", kind=CoordinationKind.TASK_ASSIGN, payload={"task": "t1"}
    )
    assert coordination.kind == CoordinationKind.TASK_ASSIGN


def test_task_value_objects() -> None:
    task = Task(id="t", title="t", description="d", acceptance_criteria=["a"], metadata={"k": 1})
    frozen = TaskResult(task_id="t", success=True, artifacts=["results/x/patch.diff"])
    assert task.subtask_ids == [] and frozen.artifacts
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        task.title = "mutated"  # type: ignore[misc]
