"""Budget governor tests (issue 2.13)."""

from __future__ import annotations

import pytest

from harness.config import BudgetConfig
from harness.engine.budget import BudgetExhausted, BudgetGovernor, GovernorMode
from harness.infrastructure.context_store import MemoryContextStore


@pytest.fixture
def store() -> MemoryContextStore:
    return MemoryContextStore()


def _governor(store: MemoryContextStore, **budget_kwargs: object) -> BudgetGovernor:
    defaults: dict[str, object] = {
        "total_tokens": 1000,
        "warn_fraction": 0.5,
        "surgical_fraction": 0.9,
    }
    defaults.update(budget_kwargs)
    return BudgetGovernor(store, BudgetConfig(**defaults), "corr-1")  # type: ignore[arg-type]


def test_modes_across_thresholds(store) -> None:
    governor = _governor(store)  # warn at 500, finalize at 900, stop at 1000
    governor.record("a-1", "m", 499, 0)
    assert governor.mode() == GovernorMode.NORMAL
    governor.record("a-1", "m", 10, 0)  # 509
    assert governor.mode() == GovernorMode.SURGICAL
    governor.record("a-1", "m", 391, 0)  # 900
    assert governor.mode() == GovernorMode.FINALIZE
    assert governor.used_tokens() == 900


def test_check_raises_at_total(store) -> None:
    governor = _governor(store)
    governor.record("a-1", "m", 999, 1)
    with pytest.raises(BudgetExhausted, match="budget exhausted"):
        governor.check()


def test_check_passes_under_budget(store) -> None:
    _governor(store).check()  # no usage yet


def test_exhausted_result_is_honest(store) -> None:
    governor = _governor(store)
    governor.record("a-1", "m", 100, 1)
    result = governor.exhausted_result("task-1")
    assert result.success is False
    assert "budget exhausted after 101 tokens" in result.error
    assert result.summary == "stopped by token budget governor"
    custom = governor.exhausted_result("task-1", summary="partial work kept")
    assert custom.summary == "partial work kept"


def test_correlation_id_and_isolation(store) -> None:
    governor = _governor(store)
    assert governor.correlation_id == "corr-1"
    governor.record("a-1", "m", 10, 5)
    other = BudgetGovernor(store, BudgetConfig(total_tokens=1000), "corr-2")
    assert other.used_tokens() == 0
    assert governor.used_tokens() == 15
