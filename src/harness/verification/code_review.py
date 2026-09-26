"""Code-review stage (milestone 3, issue 3.5): deterministic smell detection.

Pure-AST analysis (no model needed, fully deterministic) for the smells the
issue names, plus an optional LLM pass through the architect's review for
pattern-consistency judgment. Non-blocking by design: findings are
advisories, never gate failures.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

LONG_FUNCTION_LINES = 80
DEEP_NESTING_DEPTH = 5
MISSING_DOCSTRING_PUBLIC = ("def ", "class ")


@dataclass
class SmellFinding:
    path: str
    line: int
    kind: str
    detail: str


class ReviewFindings(BaseModel):
    """Serializable result of the deterministic review stage."""

    findings: list[dict[str, str]] = []
    clean: bool = True


@dataclass
class _FunctionVisitor(ast.NodeVisitor):
    findings: list[SmellFinding] = field(default_factory=list)
    path: str = ""

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        end = getattr(node, "end_lineno", node.lineno)
        if end - node.lineno + 1 > LONG_FUNCTION_LINES:
            self.findings.append(
                SmellFinding(
                    path=self.path,
                    line=node.lineno,
                    kind="long-function",
                    detail=f"'{node.name}' spans {end - node.lineno + 1} lines",
                )
            )
        if _max_nesting(node) >= DEEP_NESTING_DEPTH:
            self.findings.append(
                SmellFinding(
                    path=self.path,
                    line=node.lineno,
                    kind="deep-nesting",
                    detail=f"'{node.name}' nests {_max_nesting(node)} levels deep",
                )
            )
        if node.name.startswith("__") and node.name.endswith("__"):
            return
        if ast.get_docstring(node) is None and not node.name.startswith("_"):
            self.findings.append(
                SmellFinding(
                    path=self.path,
                    line=node.lineno,
                    kind="missing-docstring",
                    detail=f"public function '{node.name}' has no docstring",
                )
            )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)

    def visit_Try(self, node: ast.Try) -> None:
        for handler in node.handlers:
            if handler.type is None:
                self.findings.append(
                    SmellFinding(
                        path=self.path,
                        line=handler.lineno,
                        kind="bare-except",
                        detail="bare 'except:' swallows everything",
                    )
                )
        self.generic_visit(node)


def _max_nesting(node: ast.AST) -> int:
    """Deepest control-flow nesting inside one function body."""
    depth = 0

    def walk(current: ast.AST, level: int) -> None:
        nonlocal depth
        if isinstance(
            current, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncFor, ast.AsyncWith)
        ):
            level += 1
            depth = max(depth, level)
        for child in ast.iter_child_nodes(current):
            walk(child, level)

    walk(node, 0)
    return depth


def review_paths(paths: list[Path], root: Path) -> list[SmellFinding]:
    """Run the AST smells over Python files; other files are skipped."""
    findings: list[SmellFinding] = []
    for path in paths:
        if path.suffix != ".py" or not path.is_file():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue  # syntax problems are the self-check stage's job
        visitor = _FunctionVisitor(path=str(path.relative_to(root)))
        visitor.visit(tree)
        findings.extend(visitor.findings)
    return findings
