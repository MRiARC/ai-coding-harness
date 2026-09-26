"""Task value objects passed to `BaseAgent.execute_task`."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Task(BaseModel):
    """A unit of software-engineering work routed to a specialist agent."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    subtask_ids: list[str] = Field(
        default_factory=list, description="Children when the Architect decomposes a task."
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResult(BaseModel):
    """Outcome of executing a `Task`; `artifacts` are paths into the evidence pack."""

    task_id: str
    success: bool
    summary: str = ""
    artifacts: list[str] = Field(default_factory=list)
    error: str | None = None
