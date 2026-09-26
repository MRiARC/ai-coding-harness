"""Tool registry (milestone 3): the harness's default toolbelt.

One factory wires every concrete tool to a repository root. Order in the
registry does not matter; permission gating is by tier + role preset.
"""

from __future__ import annotations

from pathlib import Path

from harness.tools.base import Tool
from harness.tools.editing import ApplyEditTool, SearchTextTool, SyntaxCheckTool
from harness.tools.execution import CodeExecutionTool, RunTestsTool, SecurityScanTool
from harness.tools.filesystem import ListDirTool, ReadFileTool
from harness.tools.knowledge import KnowledgeSearchTool
from harness.tools.vcs import GitBranchTool, GitDiffTool, GitLogTool, GitStatusTool


def build_default_tools(repo_root: Path) -> list[Tool]:
    """The standard toolbelt: 5 Tier-1, 5 Tier-2, 2 Tier-3 tools."""
    root = Path(repo_root)
    return [
        # Tier 1 - basic operations (issue 3.1)
        ReadFileTool(root),
        KnowledgeSearchTool(),
        ListDirTool(root),
        SearchTextTool(root),
        GitStatusTool(root),
        GitLogTool(root),
        # Tier 2 - development operations (issue 3.2)
        ApplyEditTool(root),
        SyntaxCheckTool(root),
        RunTestsTool(root),
        GitBranchTool(root),
        GitDiffTool(root),
        # Tier 3 - advanced operations (issue 3.3)
        CodeExecutionTool(root),
        SecurityScanTool(root),
    ]


TOOL_NAMES: dict[str, int] = {
    "filesystem_read": 1, "search_knowledge": 1,
    "filesystem_list": 1,
    "search_text": 1,
    "git_status": 1,
    "git_log": 1,
    "apply_edit": 2,
    "syntax_check": 2,
    "run_tests": 2,
    "git_branch": 2,
    "git_diff": 2,
    "code_execution": 3,
    "security_scan": 3,
}


TOOL_ALIASES: dict[str, str] = {
    # Models reach for natural names; resolve them to registry instances.
    "read_file": "filesystem_read",
    "list_dir": "filesystem_list",
    "grep": "search_text",
}
