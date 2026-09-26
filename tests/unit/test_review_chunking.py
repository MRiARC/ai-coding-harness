"""Milestone 4.8: chunked, evidence-fed architect final review (audit §20).

The final gate never silently truncates: the diff is split into per-file
chunks, each reviewed via its own structured call, and files beyond the
chunk budget are named in the verdict (failing the gate honestly).
Verification evidence accompanies the review prompt.
"""

from __future__ import annotations

import json

from harness.agents.architect import ArchitectAgent, Plan, split_diff_chunks
from harness.config import BudgetConfig, ModelConfig
from harness.engine.budget import BudgetGovernor
from harness.infrastructure.context_store import MemoryContextStore
from harness.infrastructure.model_providers.base import ModelResponse
from harness.infrastructure.model_providers.fake import FakeProvider

PLAN = Plan.model_validate(
    {
        "issue_summary": "greeting",
        "complexity": 2,
        "subtasks": [
            {
                "id": "st-1",
                "title": "greet",
                "description": "",
                "specialty": "implementer",
                "complexity": 2,
                "files": ["app.py"],
                "acceptance_criteria": ["greet returns hello"],
                "depends_on": [],
            }
        ],
    }
)


def _architect(script: list[ModelResponse]) -> tuple[ArchitectAgent, FakeProvider]:
    config = ModelConfig(provider="fake", name="fake-model", api_key_env="AI_API_KEY")
    provider = FakeProvider(config, responses=script)
    store = MemoryContextStore()
    agent = ArchitectAgent(
        agent_id="arch-1",
        model_config={},
        tools=[],
        context_window=MemoryContextStore(),
        provider=provider,
        store=store,
        governor=BudgetGovernor(store, BudgetConfig(), "run-1"),
    )
    from harness.agents.llm_agent import StoreWindow

    agent.context_window = StoreWindow(store, "arch-1", "planning")
    return agent, provider


def _verdict(approved: bool, issues: list[str] | None = None) -> ModelResponse:
    return ModelResponse(
        content=json.dumps({"approved": approved, "issues": issues or [], "summary": "chunk"})
    )


def test_split_diff_chunks_single_small_diff() -> None:
    diff = "diff --git a/app.py\n+++ b/app.py\n+code\n"
    chunks, unreviewed = split_diff_chunks(diff)
    assert len(chunks) == 1
    assert unreviewed == []


def test_split_diff_chunks_groups_files_under_budget() -> None:
    file_a = "diff --git a/a.py\n+++ b/a.py\n" + "+" + "x" * 900 + "\n"
    file_b = "diff --git a/b.py\n+++ b/b.py\n" + "+" + "y" * 900 + "\n"
    chunks, unreviewed = split_diff_chunks(file_a + file_b, max_chars=2000)
    assert len(chunks) == 1  # both fit in one 2000-char chunk
    assert "a.py" in chunks[0] and "b.py" in chunks[0]
    assert unreviewed == []


def test_split_diff_chunks_flags_overflow_honestly() -> None:
    files = "".join(
        f"diff --git a/f{i}.py\n+++ b/f{i}.py\n" + "+" + "z" * 600 + "\n" for i in range(16)
    )
    chunks, unreviewed = split_diff_chunks(files, max_chars=2000)
    assert len(chunks) == 5  # capped at _MAX_REVIEW_CHUNKS
    assert unreviewed == ["f15.py"]  # the 16th file lands beyond the budget


def test_split_diff_chunks_empty() -> None:
    assert split_diff_chunks("") == ([], [])


async def test_review_single_chunk_includes_evidence() -> None:
    agent, provider = _architect([_verdict(True)])
    diff = "diff --git a/app.py\n+++ b/app.py\n+hello\n"
    verdict = await agent.review(diff, PLAN, evidence="stage2: 12/12 tests pass")
    assert verdict.approved
    prompt = provider.calls[0]["messages"][1]["content"]
    assert "VERIFICATION EVIDENCE:" in prompt
    assert "12/12 tests pass" in prompt
    assert "chunk 1/1" in prompt


async def test_review_merges_per_chunk_verdicts() -> None:
    diff = (
        "diff --git a/a.py\n+++ b/a.py\n+" + "x" * 11_000 + "\n"
        "diff --git a/b.py\n+++ b/b.py\n+" + "y" * 11_000 + "\n"
    )
    agent, provider = _architect([_verdict(True), _verdict(False, ["n+1 query"])])
    verdict = await agent.review(diff, PLAN)
    assert not verdict.approved
    assert "n+1 query" in verdict.issues
    assert len(provider.calls) == 2


async def test_review_overflow_fails_gate_honestly() -> None:
    files = "".join(
        f"diff --git a/f{i}.py\n+++ b/f{i}.py\n" + "+" + "z" * 4_500 + "\n" for i in range(12)
    )
    agent, provider = _architect([_verdict(True) for _ in range(5)])
    verdict = await agent.review(files, PLAN)
    assert not verdict.approved
    assert any("not fully reviewed" in issue for issue in verdict.issues)
    assert len(provider.calls) == 5  # budget respected


async def test_review_empty_diff_skips_calls() -> None:
    agent, provider = _architect([])
    verdict = await agent.review("", PLAN)
    assert verdict.approved
    assert "no changed files" in verdict.summary
    assert provider.calls == []
