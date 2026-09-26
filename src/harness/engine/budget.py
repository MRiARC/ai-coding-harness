"""Token budget governor (milestone 2, issue 2.13 - resource management).

Meters every model call through the context store's usage ledger and exposes
the operating mode the rest of the harness must respect:

- below `warn_fraction`      -> NORMAL
- at/above `warn_fraction`   -> SURGICAL (no re-plans, minimal exploration)
- at/above `surgical_fraction` -> FINALIZE (verify + fix failing tests only)
- at/above `total_tokens`    -> `BudgetExhausted` (stop honestly)
"""

from __future__ import annotations

from enum import StrEnum

from harness.agents.task import TaskResult
from harness.config import BudgetConfig
from harness.infrastructure.context_store import ContextStore


class BudgetExhausted(RuntimeError):  # noqa: N818 - domain state name, not an error suffix case
    """Raised when the run's token budget is spent; callers finalize gracefully."""


class GovernorMode(StrEnum):
    NORMAL = "normal"
    SURGICAL = "surgical"
    FINALIZE = "finalize"


class BudgetGovernor:
    """Per-run token meter backed by the context-store usage ledger."""

    def __init__(self, store: ContextStore, budget: BudgetConfig, correlation_id: str) -> None:
        self._store = store
        self._budget = budget
        self._correlation_id = correlation_id

    @property
    def correlation_id(self) -> str:
        return self._correlation_id

    def used_tokens(self) -> int:
        return self._store.token_usage(self._correlation_id).total_tokens

    def mode(self) -> GovernorMode:
        """Current operating mode derived from spend vs configured thresholds."""
        warn, surgical, _ = self._budget.thresholds()
        used = self.used_tokens()
        if used >= surgical:
            return GovernorMode.FINALIZE
        if used >= warn:
            return GovernorMode.SURGICAL
        return GovernorMode.NORMAL

    def check(self) -> None:
        """Raise `BudgetExhausted` when the run must stop. Cheap; call per step."""
        if self.used_tokens() >= self._budget.total_tokens:
            msg = f"token budget exhausted: {self.used_tokens()} >= {self._budget.total_tokens}"
            raise BudgetExhausted(msg)

    def record(self, agent_id: str, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        """Append one model call to the ledger."""
        self._store.record_token_usage(
            self._correlation_id, agent_id, model, prompt_tokens, completion_tokens
        )

    def exhausted_result(self, task_id: str, summary: str = "") -> TaskResult:
        """Honest failure result for a task stopped by the budget."""
        return TaskResult(
            task_id=task_id,
            success=False,
            summary=summary or "stopped by token budget governor",
            error=f"budget exhausted after {self.used_tokens()} tokens",
        )
