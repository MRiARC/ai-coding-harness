"""repo_graph tool (M5 issue #60): graph-backed localization for agents.

Builds (or loads) the repo graph and answers a query with a BFS-ranked file
neighborhood: matched seeds first, then imports/imported-by within `hops`.
This is the structured localization artifact the spec promised — files,
symbols, and graph distance instead of prose.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from harness.indexing.graph import (
    RepoGraph,
    build_repo_graph,
    load_graph,
    localize,
    save_graph,
)
from harness.tools.base import Tool, ToolResult, ToolTier


class RepoGraphTool(Tool):
    """repo_graph: BFS-ranked file neighborhood for a query (tier 1)."""

    name, tier = "repo_graph", ToolTier.BASIC
    description = (
        "Localize a task in the repo: returns files ranked by graph distance "
        "from matches of the query terms (file paths, functions, classes). "
        "Args: query (space-separated terms), hops (optional, default 2)."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "hops": {"type": "integer"},
        },
        "required": ["query"],
    }

    def __init__(self, repo_root: Path) -> None:
        self._root = Path(repo_root)
        self._db = self._root / ".harness" / "graph.db"
        self._graph: RepoGraph | None = None
        self.built_at: float | None = None

    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        return [] if arguments.get("query") else ["'query' is required"]

    def check_permissions(self, context: dict[str, Any]) -> bool:
        return True

    def _ensure_graph(self, rebuild: bool = False) -> RepoGraph:
        graph = self._graph
        if graph is None or rebuild:
            graph = load_graph(self._db)
            if rebuild or not graph.nodes:
                graph = build_repo_graph(self._root)
                save_graph(graph, self._db)
            self.built_at = time.time()
            self._graph = graph
        return graph

    def execute(self, query: str, hops: int = 2, rebuild: bool = False, **_: Any) -> ToolResult:
        graph = self._ensure_graph(rebuild=rebuild)
        if not graph.nodes:
            return ToolResult(success=True, output="repo graph is empty (no indexable files)")
        results = localize(graph, query, hops=max(0, hops))
        if not results:
            return ToolResult(
                success=True,
                output=f"no graph matches for {query!r}",
                data={"matches": 0},
            )
        lines = [
            f"{'*' if item['seed'] else ' '} d{item['distance']} {item['path']}"
            f" ({item['loc']} loc"
            + (f"; symbols: {', '.join(item['symbols'][:5])}" if item["symbols"] else "")
            + ")"
            for item in results
        ]
        return ToolResult(
            success=True,
            output="\n".join(lines),
            data={"query": query, "matches": len(results), "hops": hops},
        )
