"""Tool interface shared by every specialist agent.

Tools are the only way agents touch the repository. Each tool declares a
`ToolTier`; the access-control logic (`check_permissions`) gates advanced
operations behind capable agents, per the design's three-tier model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field


class ToolTier(IntEnum):
    """Progressive capability tiers (design spec §7)."""

    BASIC = 1  # read-only operations
    DEVELOPMENT = 2  # file writes, git, test runs
    ADVANCED = 3  # execution, network, destructive operations


class ToolResult(BaseModel):
    """Structured output of a tool invocation; always safe to log/trace."""

    success: bool
    output: str = ""
    error: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class Tool(ABC):
    """Abstract tool: metadata for the model, contract for the runtime.

    Subclasses implement the three abstract methods and must remain free of
    side effects outside `execute` (validation and permission checks are pure).
    """

    name: str
    tier: ToolTier
    description: str
    parameters: dict[str, Any]
    """JSON-schema description of `execute`'s keyword arguments."""

    @abstractmethod
    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        """Return a list of human-readable validation errors; empty means valid."""

    @abstractmethod
    def check_permissions(self, context: dict[str, Any]) -> bool:
        """Whether the calling agent (identified in `context`, e.g. by
        `agent_id` and `model_tier`) may invoke this tool."""

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Perform the tool's operation. Must never raise: return a failing
        `ToolResult` instead so the recovery ladder can reason over it."""
