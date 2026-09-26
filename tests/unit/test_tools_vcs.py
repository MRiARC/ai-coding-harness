"""Git tools + registry (issues 3.1-3.2)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness.tools.registry import TOOL_NAMES, build_default_tools
from harness.tools.vcs import GitBranchTool, GitDiffTool, GitLogTool, GitStatusTool


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    (tmp_path / "a.txt").write_text("one\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "one",
        ],
        check=True,
    )
    return tmp_path


def test_git_status_and_log(repo) -> None:
    status = GitStatusTool(repo).execute()
    assert status.success
    (repo / "b.txt").write_text("two\n")
    dirty = GitStatusTool(repo).execute()
    assert "b.txt" in dirty.output
    log = GitLogTool(repo).execute(limit=1)
    assert "one" in log.output
    assert GitLogTool(repo).validate_input({"limit": 0}) != []
    assert GitLogTool(repo).validate_input({"limit": 5}) == []


def test_git_branch_and_diff(repo) -> None:
    tool = GitBranchTool(repo)
    assert tool.execute(action="create", name="agent/x-1").success
    assert "agent/x-1" in tool.execute(action="list").output
    assert not tool.execute(action="create", name="agent/x-1").success  # exists
    (repo / "a.txt").write_text("one changed\n")
    diff = GitDiffTool(repo).execute()
    assert "one changed" in diff.output
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "main"], check=True)
    assert tool.execute(action="delete", name="agent/x-1", force=True).success
    assert tool.validate_input({"action": "create"}) != []
    assert tool.validate_input({"action": "list"}) == []
    assert GitDiffTool(repo).check_permissions({"model_tier": 1}) is False


def test_git_timeout(repo, monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git status", timeout=60)

    monkeypatch.setattr(subprocess, "run", explode)
    assert not GitStatusTool(repo).execute().success


def test_registry_builds_twelve_tools(repo) -> None:
    tools = build_default_tools(repo)
    names = [tool.name for tool in tools]
    assert len(names) == len(set(names)) == len(TOOL_NAMES)
    assert set(names) == set(TOOL_NAMES)
    tiers = {tool.name: tool.tier.value for tool in tools}
    assert tiers["filesystem_read"] == 1 and tiers["code_execution"] == 3
