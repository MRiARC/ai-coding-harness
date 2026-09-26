"""Git tools (milestone 3, issues 3.1-3.2): status, log, branch, diff.

Synchronous `git` CLI calls (tools execute synchronously; the async GitService
remains for orchestration-level flows). No push, ever: the harness works
locally in the evaluation environment.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from harness.tools.base import Tool, ToolResult, ToolTier

GIT_TIMEOUT = 60.0


def _git(repo_root: Path, *args: str) -> ToolResult:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, error=f"git {' '.join(args[:2])} timed out")
    if proc.returncode != 0:
        return ToolResult(success=False, error=f"git {' '.join(args)}: {proc.stderr.strip()[:200]}")
    return ToolResult(success=True, output=proc.stdout.strip())


class GitStatusTool(Tool):
    """git_status: working-tree state."""

    name, tier = "git_status", ToolTier.BASIC
    description = "Show the working tree status (porcelain format)."
    parameters: dict[str, Any] = {"type": "object", "properties": {}}

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root

    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        return []

    def check_permissions(self, context: dict[str, Any]) -> bool:
        return True

    def execute(self, **_: Any) -> ToolResult:
        return _git(self._root, "status", "--porcelain")


class GitLogTool(Tool):
    """git_log: recent commit history."""

    name, tier = "git_log", ToolTier.BASIC
    description = "Show recent commits (oneline). Optional 'limit'."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {"limit": {"type": "integer"}},
    }

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root

    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        limit = arguments.get("limit")
        if limit is not None and (not isinstance(limit, int) or not 1 <= limit <= 100):
            return ["'limit' must be an integer in [1, 100]"]
        return []

    def check_permissions(self, context: dict[str, Any]) -> bool:
        return True

    def execute(self, limit: int = 10, **_: Any) -> ToolResult:
        return _git(self._root, "log", "--oneline", f"-n{limit}")


class GitBranchTool(Tool):
    """git_branch: create/list/delete local branches."""

    name, tier = "git_branch", ToolTier.DEVELOPMENT
    description = (
        "Local branch operations. Args: action ('create'|'list'|'delete'), "
        "name, from_ref (for create), force (for delete). No push."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "list", "delete"]},
            "name": {"type": "string"},
            "from_ref": {"type": "string"},
            "force": {"type": "boolean"},
        },
        "required": ["action"],
    }

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root

    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        action = arguments.get("action")
        if action not in {"create", "list", "delete"}:
            return ["'action' must be create|list|delete"]
        if action in {"create", "delete"} and not arguments.get("name"):
            return [f"'name' is required for action '{action}'"]
        return []

    def check_permissions(self, context: dict[str, Any]) -> bool:
        return context.get("model_tier", 1) >= self.tier.value

    def execute(
        self,
        action: str,
        name: str | None = None,
        from_ref: str = "HEAD",
        force: bool = False,
        **_: Any,
    ) -> ToolResult:
        if action == "list":
            return _git(self._root, "branch", "--format=%(refname:short)")
        if action == "create":
            return _git(self._root, "checkout", "-b", str(name), from_ref)
        return _git(self._root, "branch", "-D" if force else "-d", str(name))


class GitDiffTool(Tool):
    """git_diff: unified diff of the working tree (the patch source)."""

    name, tier = "git_diff", ToolTier.DEVELOPMENT
    description = "Unified diff of uncommitted changes (or against a ref)."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {"ref": {"type": "string"}},
    }

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root

    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        return []

    def check_permissions(self, context: dict[str, Any]) -> bool:
        return context.get("model_tier", 1) >= self.tier.value

    def execute(self, ref: str = "HEAD", **_: Any) -> ToolResult:
        return _git(self._root, "diff", ref)


class GitAddTool(Tool):
    """git_add: intent-to-add paths so new files reach the patch (tier 2).

    Uses `git add -N` (intent-to-add): untracked files become visible to
    `git diff HEAD` — the evidence pack's patch — without staging content
    or touching the index state the evaluator may inspect.
    """

    name, tier = "git_add", ToolTier.DEVELOPMENT
    description = (
        "Record new/changed paths so they appear in the diff "
        "(intent-to-add; never stages or commits). Args: paths (array) or all=true."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "paths": {"type": "array", "items": {"type": "string"}},
            "all": {"type": "boolean"},
        },
    }

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root

    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        if arguments.get("all"):
            return []
        paths = arguments.get("paths")
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
            return ["provide 'paths' (array of strings) or all=true"]
        return []

    def check_permissions(self, context: dict[str, Any]) -> bool:
        return context.get("model_tier", 1) >= self.tier.value

    def execute(self, paths: list[str] | None = None, all: bool = False, **_: Any) -> ToolResult:
        argv = ["add", "--intent-to-add"]
        if all or not paths:
            argv.append("-A")
        else:
            argv.append("--")
            argv.extend(paths)
        return _git(self._root, *argv)
