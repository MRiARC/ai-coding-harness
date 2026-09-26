"""Knowledge-search tool (issue #78): lexical corpus lookup, Tier 1.

Every persona can consult any other persona's playbook on demand — the
verifier can pull the testing specialist's checklist, the implementer can
consult the security playbook before touching an auth path.
"""

from __future__ import annotations

from typing import Any

from harness.knowledge.registry import DEFAULT_SEARCH_LIMIT, search_knowledge
from harness.tools.base import Tool, ToolResult, ToolTier


class KnowledgeSearchTool(Tool):
    """search_knowledge: query the persona knowledge corpus."""

    name, tier = "search_knowledge", ToolTier.BASIC
    description = (
        "Search the persona knowledge corpus (playbooks: architecture, testing, "
        "security, devops, ...). Args: query (words), role (optional - default "
        "searches all personas), limit (optional)."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "role": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    }

    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        if not str(arguments.get("query", "")).strip():
            return ["'query' must be non-empty"]
        return []

    def check_permissions(self, context: dict[str, Any]) -> bool:
        return True

    def execute(self, query: str, role: str | None = None,
                limit: int = DEFAULT_SEARCH_LIMIT, **_: Any) -> ToolResult:
        findings = search_knowledge(query, role=role, limit=limit)
        if not findings:
            return ToolResult(
                success=True,
                output=f"no knowledge matches for {query!r}",
                data={"matches": 0},
            )
        lines = [
            f"[{finding['role']} / {finding['section']}] {finding['line']}"
            for finding in findings
        ]
        return ToolResult(
            success=True,
            output="\n".join(lines),
            data={"matches": len(findings)},
        )
