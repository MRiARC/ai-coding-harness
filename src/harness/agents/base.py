"""Agent base classes.

`BaseAgent` is the contract every role (Architect, Manager, specialists)
implements; `BaseManager` extends it with coordination responsibilities.
Subclasses own *behavior*; this module only defines the contract, per
foundation issue 1.2 (no orchestration logic here).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

from harness.agents.task import Task, TaskResult
from harness.orchestration.messages import ErrorEscalation, StatusUpdate
from harness.tools.base import Tool


@runtime_checkable
class ContextWindow(Protocol):
    """Read/write view over an agent's conversation context.

    Implemented by the context-store infrastructure (foundation issue 1.4);
    agents depend on this protocol, never on the storage backend.
    """

    def append(self, role: str, content: str) -> None:
        """Record one turn (role is 'system' | 'user' | 'assistant' | 'tool')."""

    def as_messages(self) -> list[dict[str, str]]:
        """Return the window in OpenAI chat format for the model provider."""


class BaseAgent(ABC):
    """Common contract for all agents in the hierarchy.

    Attributes:
        agent_id: Unique identifier used in protocol messages and traces.
        model_config: Raw "model" section of the harness configuration
            (provider, model name, temperature); interpreted by the
            model-provider layer, never by the agent itself.
        tools: Tools this agent may invoke, gated by `Tool.check_permissions`.
        context_window: The agent's conversation context view.
    """

    agent_id: str
    model_config: dict[str, Any]
    tools: Sequence[Tool]
    context_window: ContextWindow

    def __init__(
        self,
        agent_id: str,
        model_config: dict[str, Any],
        tools: Sequence[Tool],
        context_window: ContextWindow,
    ) -> None:
        self.agent_id = agent_id
        self.model_config = model_config
        self.tools = tools
        self.context_window = context_window

    @abstractmethod
    def execute_task(self, task: Task) -> TaskResult:
        """Run a task to completion (including the agent's internal loop)."""

    @abstractmethod
    def handle_error(self, error: Exception, task: Task) -> ErrorEscalation:
        """Classify a failure into an `ErrorEscalation` for the recovery ladder."""

    @abstractmethod
    def report_status(self) -> StatusUpdate:
        """Publish the agent's current lifecycle state."""

    def permitted_tools(self, context: dict[str, Any]) -> list[Tool]:
        """Tools this agent may use given its declared capabilities.

        This is shared behavior (not per-role logic), so it is concrete.
        """
        return [tool for tool in self.tools if tool.check_permissions(context)]


class BaseManager(BaseAgent):
    """Coordination-tier agent: routes work, watches progress, absorbs escalations.

    Extends `BaseAgent` with the Manager responsibilities from the design's
    three-tier hierarchy (Architect -> Managers -> Specialists).
    """

    @abstractmethod
    def assign_task(self, task: Task, agent_id: str) -> None:
        """Route `task` to the named specialist."""

    @abstractmethod
    def monitor_progress(self) -> list[StatusUpdate]:
        """Collect recent status updates from assigned specialists."""

    @abstractmethod
    def handle_escalation(self, escalation: ErrorEscalation) -> StatusUpdate:
        """Decide and execute the response to a specialist's escalation."""
