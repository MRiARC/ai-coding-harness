"""M5 issue #60: repo context graph — build, SQLite persistence, BFS
retrieval, and the repo_graph tool (the structured localization artifact)."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.agents.llm_agent import LLMAgent, StoreWindow
from harness.agents.task import Task
from harness.config import BudgetConfig, ModelConfig
from harness.engine.budget import BudgetGovernor
from harness.indexing.graph import (
    bfs_neighborhood,
    build_repo_graph,
    load_graph,
    localize,
    match_seeds,
    save_graph,
)
from harness.infrastructure.context_store import MemoryContextStore
from harness.infrastructure.model_providers.base import ModelResponse, ToolCall
from harness.infrastructure.model_providers.fake import FakeProvider
from harness.tools.graph import RepoGraphTool


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "app.py").write_text(
        "from helpers import format_task\n"
        "from models import Task\n\n"
        "def add_task(tasks, title):\n"
        "    tasks.append(Task(title=title))\n"
        "    return format_task(tasks[-1])\n"
    )
    (tmp_path / "helpers.py").write_text("def format_task(task):\n    return str(task)\n")
    (tmp_path / "models.py").write_text(
        "class Task:\n    def __init__(self, title):\n        self.title = title\n"
    )
    (tmp_path / "broken.py").write_text("def oops(:\n")  # syntax error: tolerated
    (tmp_path / "escaper.py").write_text("from .. import outside_repo\n")
    (tmp_path / "README.md").write_text("docs\n")  # non-python node
    return tmp_path


def test_build_collects_nodes_symbols_and_edges(repo: Path) -> None:
    graph = build_repo_graph(repo)
    assert {"app.py", "helpers.py", "models.py", "README.md"} <= set(graph.nodes)
    assert graph.nodes["app.py"].symbols == ["add_task"]
    assert graph.nodes["models.py"].symbols == ["Task"]
    assert graph.edges["app.py"] == {"helpers.py", "models.py"}


def test_build_respects_max_files(repo: Path) -> None:
    graph = build_repo_graph(repo, max_files=2)
    assert len(graph.nodes) == 2


def test_bfs_neighborhood_distances(repo: Path) -> None:
    graph = build_repo_graph(repo)
    distances = bfs_neighborhood(graph, ["app.py"], hops=2)
    assert distances["app.py"] == 0
    assert distances["helpers.py"] == 1
    assert distances["models.py"] == 1


def test_match_seeds_rank_by_hits(repo: Path) -> None:
    graph = build_repo_graph(repo)
    seeds = match_seeds(graph, "add_task")
    assert seeds[0] == "app.py"
    assert match_seeds(graph, "nothing-matches-this") == []


def test_localize_seeds_first_then_bfs(repo: Path) -> None:
    graph = build_repo_graph(repo)
    results = localize(graph, "format_task", hops=1)
    assert results[0]["path"] == "helpers.py" and results[0]["seed"]
    assert any(r["path"] == "app.py" and r["distance"] == 1 for r in results)
    assert all("seed" in r for r in results)


def test_sqlite_persistence_roundtrip(repo: Path, tmp_path: Path) -> None:
    graph = build_repo_graph(repo)
    db = tmp_path / "graph.db"
    save_graph(graph, db)
    loaded = load_graph(db)
    assert set(loaded.nodes) == set(graph.nodes)
    assert loaded.edges["app.py"] == graph.edges["app.py"]
    assert load_graph(tmp_path / "missing.db").nodes == {}


def test_tool_returns_bfs_ranked_output(repo: Path) -> None:
    tool = RepoGraphTool(repo)
    result = tool.execute(query="add_task", hops=1)
    assert result.success
    assert "d0 app.py" in result.output
    assert "d1 helpers.py" in result.output
    assert result.data["matches"] >= 2
    # second call uses the cached graph + persisted db
    again = tool.execute(query="Task", hops=0)
    assert again.success


def test_tool_empty_graph_and_no_match(tmp_path: Path) -> None:
    tool = RepoGraphTool(tmp_path)  # no files at all
    assert tool.execute(query="anything").success
    empty = RepoGraphTool(tmp_path / "nonexistent")
    assert "empty" in empty.execute(query="x").output
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "only.txt").write_text("no python here")
    no_match = RepoGraphTool(tmp_path / "r").execute(query="zzz")
    assert "no graph matches" in no_match.output
    assert RepoGraphTool(tmp_path / "r").validate_input({}) == ["'query' is required"]


async def test_locator_uses_repo_graph_via_agent_loop(repo: Path) -> None:
    """End to end: the locator's loop calls repo_graph and gets localization."""
    config = ModelConfig(provider="fake", name="fake", api_key_env="AI_API_KEY")
    provider = FakeProvider(
        config,
        responses=[
            ModelResponse(
                content="",
                tool_calls=[
                    ToolCall(id="g1", name="repo_graph", arguments={"query": "add_task", "hops": 1})
                ],
            ),
            ModelResponse(content="TASK_COMPLETE: localized to app.py + helpers.py"),
        ],
    )
    store = MemoryContextStore()
    from harness.tools.registry import build_default_tools

    tools = [t for t in build_default_tools(repo) if t.name == "repo_graph"]
    agent = LLMAgent(
        agent_id="locator-1",
        model_config={},
        tools=tools,
        context_window=StoreWindow(store, "locator-1", "task-1"),
        provider=provider,
        store=store,
        governor=BudgetGovernor(store, BudgetConfig(), "run-1"),
        role="locator",
    )
    result = await agent.execute_task(
        Task(id="task-1", title="Localize", description="find add_task")
    )
    assert result.success
    window = store.load_agent_context("locator-1", "task-1").recent
    tool_turn = next(t for t in window if t.role == "tool")
    assert "d0 app.py" in tool_turn.content


def test_relative_imports_and_package_resolution(tmp_path: Path) -> None:
    """Level-based relative imports and package __init__ files resolve."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "core.py").write_text("VALUE = 1\n")
    (pkg / "user.py").write_text(
        "from . import core\nfrom .core import VALUE\nfrom os import path\n"
    )
    graph = build_repo_graph(tmp_path)
    assert graph.edges["pkg/user.py"] >= {"pkg/core.py"}


def test_external_imports_are_dropped(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("import requests\nfrom flask import Flask\n")
    graph = build_repo_graph(tmp_path)
    assert graph.edges["app.py"] == set()


def test_max_files_cap_stops_walk(tmp_path: Path) -> None:
    for i in range(6):
        (tmp_path / f"m{i}.py").write_text(f"x{i} = {i}\n")
    graph = build_repo_graph(tmp_path, max_files=3)
    assert len(graph.nodes) == 3


def test_skip_dirs_and_suffixes(tmp_path: Path) -> None:
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "v.py").write_text("v = 1\n")
    (tmp_path / "data.db").write_text("binary")
    graph = build_repo_graph(tmp_path)
    assert graph.nodes == {}


async def test_repo_graph_tool_rebuild_flag(memory_store, repo) -> None:
    """rebuild=True forces re-indexing even when a cached graph exists."""
    tool = RepoGraphTool(repo)
    tool.execute(query="add_task")
    stale = tool._graph
    tool.execute(query="add_task", rebuild=True)
    assert tool._graph is not stale and tool.built_at is not None


def test_deep_relative_imports_and_output_cap(tmp_path: Path) -> None:
    """level>=2 relative imports and the MAX_GRAPH_OUTPUT cap are covered."""
    pkg = tmp_path / "pkg"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "sub" / "__init__.py").write_text("")
    (pkg / "sub" / "deep.py").write_text("DEPTH = 2\n")
    (pkg / "sub" / "user.py").write_text(
        "from ..sub import deep\nfrom ..sub.deep import DEPTH\n"
        "from .. import core\nfrom . import __init__ as noop\n"
    )
    graph = build_repo_graph(tmp_path)
    assert "pkg/sub/deep.py" in graph.edges["pkg/sub/user.py"]

    # Output cap: many seeds within hops flood the localization list.
    for i in range(40):
        (tmp_path / f"c{i}.py").write_text(f"def marker_{i}():\n    return {i}\n")
    graph2 = build_repo_graph(tmp_path)
    query = " ".join(f"marker_{i}" for i in range(40))
    results = localize(graph2, query, hops=1)
    assert len(results) <= 30  # MAX_GRAPH_OUTPUT
