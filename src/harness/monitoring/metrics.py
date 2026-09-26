"""Metrics collection (milestone 3, issue 3.11).

Aggregates the run's story from the context store's usage ledger and task
results: tokens per agent, tasks completed/failed, efficiency (tasks per 1k
tokens), and per-stage durations. Zero infrastructure - the store already
has everything; this module just reads it into shapes the evidence pack and
TUI can render.
"""

from __future__ import annotations

from typing import Any

from harness.agents.task import TaskResult
from harness.engine.budget import BudgetGovernor
from harness.infrastructure.context_store import ContextStore


class MetricsCollector:
    """Builds agent/task/system metrics for one run (correlation id)."""

    def __init__(self, store: ContextStore, governor: BudgetGovernor) -> None:
        self._store = store
        self._governor = governor
        self._results: list[tuple[str, TaskResult]] = []
        self._stage_durations: dict[str, float] = {}
        self._start_marker: dict[str, float] = {}

    def record_result(self, result: TaskResult, agent_id: str = "") -> None:
        """Count one finished task; `agent_id` attributes tokens to work."""
        self._results.append((agent_id or result.task_id, result))

    def stage_started(self, name: str) -> None:
        import time

        self._start_marker[name] = time.monotonic()

    def stage_finished(self, name: str) -> float:
        import time

        started = self._start_marker.pop(name, None)
        if started is None:
            return 0.0
        duration = round(time.monotonic() - started, 3)
        self._stage_durations[name] = duration
        return duration

    def agent_usage(self) -> dict[str, dict[str, int]]:
        """Token ledger rows grouped by agent (requires SQL access on the store)."""
        from harness.infrastructure.context_store import SQLiteContextStore

        usage: dict[str, dict[str, int]] = {}
        if isinstance(self._store, SQLiteContextStore):
            rows = self._store._conn.execute(
                "SELECT agent_id, SUM(prompt_tokens), SUM(completion_tokens) "
                "FROM token_usage WHERE correlation_id = ? GROUP BY agent_id",
                (self._governor.correlation_id,),
            ).fetchall()
            for agent_id, prompt, completion in rows:
                usage[agent_id] = {
                    "prompt_tokens": int(prompt),
                    "completion_tokens": int(completion),
                    "total_tokens": int(prompt) + int(completion),
                }
        return usage

    def efficiency(self) -> dict[str, float]:
        """Tasks per 1k tokens per agent (DESIGN_SPEC §11 efficiency score)."""
        scores: dict[str, float] = {}
        per_agent: dict[str, int] = {}
        for agent_id, result in self._results:
            per_agent[agent_id] = per_agent.get(agent_id, 0) + (1 if result.success else 0)
        for agent_id, tokens in self.agent_usage().items():
            completed = per_agent.get(agent_id, 0)
            scores[agent_id] = (
                round(completed / (tokens["total_tokens"] / 1000), 3)
                if tokens["total_tokens"]
                else 0.0
            )
        return scores

    def report(self) -> dict[str, Any]:
        """Full metrics snapshot: system, per-agent, per-task, stages."""
        completed = sum(1 for _, r in self._results if r.success)
        failed = len(self._results) - completed
        usage = self.agent_usage()
        return {
            "correlation_id": self._governor.correlation_id,
            "tokens_total": self._governor.used_tokens(),
            "budget_total": self._governor._budget.total_tokens,
            "governor_mode": self._governor.mode().value,
            "tasks_completed": completed,
            "tasks_failed": failed,
            "tasks_per_1k_tokens": round(completed / (self._governor.used_tokens() / 1000), 3)
            if self._governor.used_tokens()
            else 0.0,
            "per_agent_tokens": usage,
            "per_agent_efficiency": self.efficiency(),
            "stage_durations": dict(self._stage_durations),
            "results": [r.model_dump() for _, r in self._results],
        }
