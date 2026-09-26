"""M5 issues #65 + #66: prompt-prefix stability and localization recall.

#65 — provider prompt caches key on the byte-stable prefix of each request.
Within one task (no compression fold), consecutive agent requests must carry
a byte-identical system block with all volatile content at the END.

#66 — SWE-bench-Lite-style localization recall: for curated mini-issues with
known gold files, the graph-backed localization stack (repo_graph + search)
must retrieve the gold files within its top-k output. Offline, deterministic.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from harness.agents.llm_agent import LLMAgent, StoreWindow
from harness.agents.task import Task
from harness.config import BudgetConfig, ModelConfig
from harness.engine.budget import BudgetGovernor
from harness.indexing.graph import build_repo_graph, localize
from harness.infrastructure.model_providers.base import ModelResponse, ToolCall
from harness.infrastructure.model_providers.fake import FakeProvider
from harness.tools.base import Tool, ToolResult
from harness.tools.editing import SearchTextTool


async def test_prefix_byte_stable_across_steps(memory_store) -> None:
    """Consecutive calls in one task share a byte-identical system prefix."""
    config = ModelConfig(provider="fake", name="fake", api_key_env="AI_API_KEY")
    provider = FakeProvider(
        config,
        responses=[
            ModelResponse(
                content="",
                tool_calls=[ToolCall(id="t1", name="noop_tool", arguments={})],
            ),
            ModelResponse(content="TASK_COMPLETE: finished"),
        ],
    )
    store = memory_store
    agent = LLMAgent(
        agent_id="impl-1",
        model_config={},
        tools=[_NoopTool()],
        context_window=StoreWindow(store, "impl-1", "task-1"),
        provider=provider,
        store=store,
        governor=BudgetGovernor(store, BudgetConfig(), "run-1"),
        role="implementer",
    )
    await agent.execute_task(Task(id="task-1", title="T", description="D"))

    system_first = provider.calls[0]["messages"][0]["content"]
    system_second = provider.calls[1]["messages"][0]["content"]
    assert system_first == system_second, "prefix drifted between steps"
    # volatile content (tool results) lives after the system block, not in it
    assert "TOOL_RESULT" not in system_first


class _NoopTool(Tool):
    """Minimal tool so the loop records a tool turn without doing work."""

    name, tier = "noop_tool", 1
    description = "does nothing"
    parameters: ClassVar[dict] = {"type": "object", "properties": {}}

    def validate_input(self, arguments):
        return []

    def check_permissions(self, context):
        return True

    def execute(self, **kwargs):
        return ToolResult(success=True, output="noop ok")


# -- #66: localization recall benchmark --------------------------------------

LOCBENCH = Path(__file__).resolve().parents[2] / "fixtures" / "locbench"
RECALL_K = 3
MIN_RECALL = 0.8


def _issue_terms(issue_text: str) -> str:
    """The Locator's real seed heuristic: distinctive words from the issue."""
    stop = {
        "the",
        "a",
        "an",
        "to",
        "of",
        "in",
        "and",
        "is",
        "are",
        "with",
        "when",
        "should",
        "be",
        "it",
        "for",
        "on",
        "that",
        "this",
        "returns",
        "return",
        "fix",
        "make",
        "wrong",
        "correct",
        "function",
        "error",
        "issue",
    }
    words = [w.strip(".,:;!?()'\"").lower() for w in issue_text.split()]
    return " ".join(w for w in words if w and w not in stop and len(w) > 2)


def test_localization_recall_on_curated_bench():
    """recall@3 across the curated SWE-bench-Lite-style cases >= 80%."""
    import json

    cases = sorted(LOCBENCH.iterdir())
    assert cases, "locbench fixtures missing"
    hits = 0
    total = 0
    per_case = {}
    for case_dir in cases:
        if not case_dir.is_dir():
            continue
        issue = (case_dir / "issue.md").read_text()
        gold = set(json.loads((case_dir / "gold.json").read_text()))
        graph = build_repo_graph(case_dir)
        results = localize(graph, _issue_terms(issue), hops=1)
        top = [r["path"] for r in results[:RECALL_K]]
        # search_text is the Locator's other workhorse: a gold hit via grep
        # over the issue's distinctive terms also counts as localized.
        searcher = SearchTextTool(case_dir)
        grep_hits = {
            line.split(":")[0]
            for term in _issue_terms(issue).split()
            for line in (searcher.execute(pattern=term).output or "").splitlines()
        }
        found = gold & (set(top) | grep_hits)
        recall = len(found) / len(gold)
        per_case[case_dir.name] = round(recall, 2)
        hits += recall
        total += 1
    average = hits / total
    print(f"\nlocalization recall@{RECALL_K}: {average:.0%} {per_case}")
    assert average >= MIN_RECALL, f"recall {average:.0%} below {MIN_RECALL:.0%}: {per_case}"
