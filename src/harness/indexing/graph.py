"""Repo context graph (M5 issue #60): nodes, edges, BFS retrieval.

Builds a lightweight whole-repo graph without external dependencies: every
file is a node; Python files contribute top-level symbols (functions,
classes) and import edges resolved to local files (stdlib `ast`, no
tree-sitter). Persisted to SQLite (`.harness/graph.db`) so the Locator and
other agents can retrieve a file's neighborhood by BFS from matched seeds —
the structured localization artifact the spec promised.
"""

from __future__ import annotations

import ast
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.tools.filesystem import SKIP_DIRS, SKIP_SUFFIXES

MAX_GRAPH_FILES = 1_500
MAX_GRAPH_OUTPUT = 30


@dataclass
class GraphNode:
    """One file in the repo graph."""

    path: str
    loc: int = 0
    symbols: list[str] = field(default_factory=list)


@dataclass
class RepoGraph:
    """Files as nodes; Python imports as directed edges (importer → imported)."""

    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: dict[str, set[str]] = field(default_factory=dict)

    def adjacency(self) -> dict[str, set[str]]:
        """Undirected view: imports + imported-by (BFS runs over this)."""
        undirected: dict[str, set[str]] = {path: set() for path in self.nodes}
        for src, dsts in self.edges.items():
            for dst in dsts:
                undirected.setdefault(src, set()).add(dst)
                undirected.setdefault(dst, set()).add(src)
        return undirected


def _module_candidates(module: str, importer_dir: Path, repo_root: Path) -> list[Path]:
    """Possible local files for an imported module name."""
    base = module.replace(".", "/")
    candidates = []
    for anchor in (repo_root, importer_dir):
        candidates.append(anchor / f"{base}.py")
        candidates.append(anchor / base / "__init__.py")
    return candidates


def _resolve_candidates(candidates: list[Path], repo_root: Path) -> set[str]:
    """Keep candidates that exist inside the repo, as repo-relative paths."""
    resolved: set[str] = set()
    for candidate in candidates:
        try:
            rel = candidate.resolve().relative_to(repo_root.resolve()).as_posix()
        except (ValueError, OSError):
            continue
        if candidate.is_file():
            resolved.add(rel)
    return resolved


def _python_file_facts(path: Path, repo_root: Path) -> tuple[list[str], set[str]]:
    """(top-level symbols, locally-resolved import targets) for one .py file."""
    symbols: list[str] = []
    imports: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (SyntaxError, ValueError, OSError):
        return symbols, imports
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.update(_resolve_import(alias.name, path, repo_root))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.update(_resolve_import(node.module, path, repo_root, level=node.level))
            if node.level:  # `from . import sibling` — names are local modules
                anchor = path.parent
                for _ in range(node.level - 1):
                    anchor = anchor.parent
                for alias in node.names:
                    candidates = [
                        anchor / f"{alias.name}.py",
                        anchor / alias.name / "__init__.py",
                    ]
                    imports.update(_resolve_candidates(candidates, repo_root))
    return symbols, imports


def _resolve_import(module: str, importer: Path, repo_root: Path, level: int = 0) -> set[str]:
    """Resolve an import to repo-relative file paths (empty if external)."""
    if level:  # relative import: anchor at the importer's package
        anchor = importer.parent
        for _ in range(level - 1):
            anchor = anchor.parent
        base = module.replace(".", "/") if module else ""
        candidates = [
            anchor / f"{base}.py" if base else anchor / "__init__.py",
            anchor / base / "__init__.py" if base else anchor / "__init__.py",
        ]
    else:
        candidates = _module_candidates(module, importer.parent, repo_root)
    return _resolve_candidates(candidates, repo_root)


def build_repo_graph(repo_root: Path, max_files: int = MAX_GRAPH_FILES) -> RepoGraph:
    """Walk the repo, collect file nodes, symbols, and local import edges."""
    repo_root = Path(repo_root)
    graph = RepoGraph()
    paths: list[Path] = []
    for candidate in sorted(repo_root.rglob("*")):
        if not candidate.is_file() or candidate.suffix in SKIP_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in candidate.parts):
            continue
        paths.append(candidate)
        if len(paths) >= max_files:
            break
    for path in paths:
        rel = path.relative_to(repo_root).as_posix()
        symbols: list[str] = []
        imports: set[str] = set()
        if path.suffix == ".py":
            symbols, imports = _python_file_facts(path, repo_root)
        graph.nodes[rel] = GraphNode(
            path=rel,
            loc=len(path.read_text(encoding="utf-8", errors="replace").splitlines()),
            symbols=symbols,
        )
        graph.edges[rel] = imports
    return graph


def save_graph(graph: RepoGraph, db_path: Path) -> Path:
    """Persist nodes + edges to SQLite (issue #60's storage contract)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    with conn:
        conn.executescript(
            "CREATE TABLE IF NOT EXISTS graph_nodes ("
            " path TEXT PRIMARY KEY, loc INTEGER, symbols TEXT);"
            "CREATE TABLE IF NOT EXISTS graph_edges ("
            " src TEXT, dst TEXT, PRIMARY KEY (src, dst));"
        )
        conn.execute("DELETE FROM graph_nodes")
        conn.execute("DELETE FROM graph_edges")
        conn.executemany(
            "INSERT INTO graph_nodes(path, loc, symbols) VALUES(?, ?, ?)",
            [(node.path, node.loc, json.dumps(node.symbols)) for node in graph.nodes.values()],
        )
        conn.executemany(
            "INSERT INTO graph_edges(src, dst) VALUES(?, ?)",
            [(src, dst) for src, dsts in graph.edges.items() for dst in dsts],
        )
    conn.close()
    return db_path


def load_graph(db_path: Path) -> RepoGraph:
    """Rehydrate a graph saved by `save_graph` (empty if the file is absent)."""
    graph = RepoGraph()
    if not Path(db_path).is_file():
        return graph
    conn = sqlite3.connect(db_path)
    for path, loc, symbols in conn.execute("SELECT path, loc, symbols FROM graph_nodes"):
        graph.nodes[path] = GraphNode(path=path, loc=loc, symbols=json.loads(symbols))
    for src, dst in conn.execute("SELECT src, dst FROM graph_edges"):
        graph.edges.setdefault(src, set()).add(dst)
    conn.close()
    return graph


def match_seeds(graph: RepoGraph, query: str) -> list[str]:
    """Files matching any query term in path or symbols, best-match first."""
    terms = [t.lower() for t in query.split() if t]
    scored: list[tuple[int, str]] = []
    for path, node in graph.nodes.items():
        haystack = f"{path} {' '.join(node.symbols)}".lower()
        hits = sum(1 for term in terms if term in haystack)
        if hits:
            scored.append((hits, path))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [path for _, path in scored]


def bfs_neighborhood(graph: RepoGraph, seeds: list[str], hops: int = 2) -> dict[str, int]:
    """BFS over the undirected graph from the seeds; returns path → distance."""
    adjacency = graph.adjacency()
    distances: dict[str, int] = {seed: 0 for seed in seeds if seed in adjacency}
    frontier = list(distances)
    for depth in range(1, hops + 1):
        nxt: list[str] = []
        for current in frontier:
            for neighbor in adjacency.get(current, set()):
                if neighbor not in distances:
                    distances[neighbor] = depth
                    nxt.append(neighbor)
        frontier = nxt
        if not frontier:
            break
    return dict(sorted(distances.items(), key=lambda pair: (pair[1], pair[0])))


def localize(graph: RepoGraph, query: str, hops: int = 2) -> list[dict[str, Any]]:
    """Match seeds, expand by BFS, and render the ranked localization."""
    seeds = match_seeds(graph, query)
    distances = bfs_neighborhood(graph, seeds, hops=hops)
    output: list[dict[str, Any]] = []
    for path, distance in distances.items():
        node = graph.nodes.get(path)
        output.append(
            {
                "path": path,
                "distance": distance,
                "loc": node.loc if node else 0,
                "symbols": node.symbols if node else [],
                "seed": path in seeds,
            }
        )
        if len(output) >= MAX_GRAPH_OUTPUT:
            break
    return output
