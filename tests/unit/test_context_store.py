"""Context-store tests over every backend (foundation issue 1.4)."""

from __future__ import annotations

from harness.infrastructure.context_store import (
    AgentContext,
    compress_ratio_before_after,
)


def test_global_context_roundtrip(store) -> None:
    store.save_global("rules", {"standards": ["typed", "linted"]})
    assert store.load_global("rules") == {"standards": ["typed", "linted"]}
    assert store.load_global("missing") is None


def test_agent_window_roundtrip(store) -> None:
    for i in range(5):
        store.append_turn("impl-1", "task-1", "user", f"msg {i}")
    ctx = store.load_agent_context("impl-1", "task-1")
    assert [t.seq for t in ctx.recent] == list(range(5))
    assert ctx.next_seq == 5


def test_save_agent_context_preserves_summary_and_milestones(store) -> None:
    ctx = store.load_agent_context("impl-1", "task-1")
    ctx.summary = "decided to use regex"
    ctx.milestones = ["localized parser.py"]
    store.save_agent_context(ctx)
    reloaded = store.load_agent_context("impl-1", "task-1")
    assert reloaded.summary == "decided to use regex"
    assert reloaded.milestones == ["localized parser.py"]


def test_compression_folds_oldest_turns(store) -> None:
    for i in range(30):
        store.append_turn(
            "impl-1", "task-1", "assistant" if i % 2 else "user", f"decision {i} " + "x" * 500
        )
    folded = store.compress("impl-1", "task-1", keep_recent=10)
    assert folded == 20
    ctx = store.load_agent_context("impl-1", "task-1")
    assert len(ctx.recent) == 10
    assert ctx.summary  # summary is populated


def test_compression_reduces_folded_storage_by_more_than_60_percent(store) -> None:
    """Acceptance criterion from issue 1.4: compression reduces storage by >60%."""
    ratio = compress_ratio_before_after(store, "impl-1", "task-1", n_turns=30, content_len=500)
    assert ratio > 0.60, ratio


def test_summary_is_capped(store) -> None:
    for _ in range(100):
        store.append_turn("cap-1", "task-1", "assistant", "y" * 400)
    for _ in range(60):
        store.compress("cap-1", "task-1", keep_recent=5)
    assert len(store.load_agent_context("cap-1", "task-1").summary) <= 4200


def test_custom_summarizer_is_used(store) -> None:
    for i in range(10):
        store.append_turn("impl-1", "task-1", "user", f"m{i}")
    folded = store.compress(
        "impl-1", "task-1", keep_recent=2, summarize=lambda turns: f"LLM-SUMMARY({len(turns)})"
    )
    assert folded == 8
    assert "LLM-SUMMARY(8)" in store.load_agent_context("impl-1", "task-1").summary


def test_neighbor_retrieval(store) -> None:
    store.append_turn("impl-1", "task-1", "user", "working")
    store.append_turn("verifier-1", "task-1", "assistant", "verifying")
    store.append_turn("impl-2", "task-2", "user", "other task")
    neighbor_ids = [n.agent_id for n in store.neighbors("impl-1", "task-1")]
    assert neighbor_ids == ["verifier-1"]


def test_token_usage_ledger(store) -> None:
    store.record_token_usage("corr-1", "impl-1", "m", 100, 50)
    store.record_token_usage("corr-1", "verifier-1", "m", 10, 5)
    store.record_token_usage("corr-2", "impl-1", "m", 7, 3)
    usage = store.token_usage("corr-1")
    assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (110, 55, 165)
    assert store.token_usage("corr-2").total_tokens == 10
    assert store.token_usage("unknown").total_tokens == 0


def test_milestones_survive_compression(store) -> None:
    ctx = AgentContext(agent_id="impl-1", task_id="task-1", milestones=["done step 1"])
    store.save_agent_context(ctx)
    for i in range(10):
        store.append_turn("impl-1", "task-1", "user", f"m{i}")
    store.compress("impl-1", "task-1", keep_recent=2)
    assert store.load_agent_context("impl-1", "task-1").milestones == ["done step 1"]
