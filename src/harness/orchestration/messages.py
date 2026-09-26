"""Protocol messages exchanged between agents.

These are the vocabulary of the coordination layer: the Architect issues
`CommandMessage`s, specialists publish `StatusUpdate`s, failures travel as
`ErrorEscalation`s, and the Manager's routing decisions are `CoordinationMessage`s.
All messages are immutable pydantic models so they can be safely shared,
serialized into evidence traces, and replayed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AgentStatus(StrEnum):
    """Lifecycle state published by an agent via `StatusUpdate`."""

    IDLE = "idle"
    WORKING = "working"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"


class Severity(StrEnum):
    """How serious an `ErrorEscalation` is; drives the recovery ladder."""

    TRANSIENT = "transient"  # retry in place (level 1)
    RECOVERABLE = "recoverable"  # manager should re-route (level 2)
    FATAL = "fatal"  # architect must re-plan (level 3)


class CoordinationKind(StrEnum):
    """Purpose of a `CoordinationMessage` sent by the Manager."""

    TASK_ASSIGN = "task_assign"
    TASK_RESULT = "task_result"
    CONTEXT_SHARE = "context_share"
    BROADCAST = "broadcast"
    SHUTDOWN = "shutdown"


class _Message(BaseModel):
    """Base for all protocol messages: frozen, correlated, timestamped."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: uuid4().hex)
    correlation_id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Ties all messages belonging to one task run together.",
    )
    created_at: datetime = Field(default_factory=_utcnow)


class CommandMessage(_Message):
    """An instruction from one agent to another (e.g. Architect -> Manager)."""

    sender: str
    recipient: str
    command: str
    payload: dict[str, Any] = Field(default_factory=dict)


class StatusUpdate(_Message):
    """A progress heartbeat published by an agent; consumed by the Manager/TUI."""

    sender: str
    status: AgentStatus
    task_id: str | None = None
    detail: str = ""


class ErrorEscalation(_Message):
    """A failure raised up the recovery ladder with evidence attached."""

    sender: str
    task_id: str | None = None
    severity: Severity
    error_type: str
    message: str
    attempt: int = 1
    suggested_action: str | None = Field(
        default=None,
        description="Optional hint for the receiving level (retry / re-route / re-plan).",
    )


class CoordinationMessage(_Message):
    """Manager-authored routing/coordination traffic."""

    sender: str
    recipient: str
    kind: CoordinationKind
    payload: dict[str, Any] = Field(default_factory=dict)
