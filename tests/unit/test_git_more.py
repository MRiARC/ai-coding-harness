"""Extended GitService tests: timeout, clone, add-by-default (issue 1.6)."""

from __future__ import annotations

import asyncio
import subprocess

import pytest

from harness.infrastructure.git_local import GIT_TIMEOUT_SECONDS, GitError, GitService


async def test_command_timeout_raises_giterror(git_ready, monkeypatch) -> None:
    async def instant_timeout(_awaitable, timeout=None):
        raise TimeoutError()

    monkeypatch.setattr(git_ready, "repo_path", git_ready.repo_path)
    import harness.infrastructure.git_local as git_local

    monkeypatch.setattr(git_local, "GIT_TIMEOUT_SECONDS", 0.001)
    monkeypatch.setattr(asyncio, "wait_for", instant_timeout)
    with pytest.raises(GitError, match="timed out"):
        await git_ready.status()


async def test_add_without_paths_stages_everything(git_ready) -> None:
    git = git_ready
    (git.repo_path / "one.txt").write_text("1\n")
    (git.repo_path / "two.txt").write_text("2\n")
    await git.add()  # no paths -> git add -A
    status = await git.status()
    assert "one.txt" in status and "two.txt" in status


async def test_clone_into_service_repo(tmp_path) -> None:
    source = tmp_path / "origin"
    source.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(source)], check=True)
    (source / "readme.md").write_text("hello\n")
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-qm",
            "init",
        ],
        check=True,
    )

    git = GitService(tmp_path / "copy")
    await git.clone(str(source))
    assert (git.repo_path / "readme.md").exists()
    assert await git.current_branch() == "main"


async def test_timeout_constant_is_sane() -> None:
    assert GIT_TIMEOUT_SECONDS >= 30


async def test_diff_against_ref(git_ready) -> None:
    git = git_ready
    (git.repo_path / "f.txt").write_text("v1\n")
    await git.add("f.txt")
    await git.commit("v1")
    (git.repo_path / "f.txt").write_text("v2\n")
    await git.add("f.txt")
    # unstaged-vs-index is empty (change is staged); vs HEAD it shows v2
    assert await git.diff("WORKING") == ""
    assert "v2" in await git.diff("HEAD")


async def test_commit_signs_locally_when_identity_unset(git_repo) -> None:
    """No repo-local identity set: commit() must sign itself (CI/eval path)."""
    git = git_repo
    await git.init()
    (git.repo_path / "f.txt").write_text("x\n")
    await git.add("f.txt")
    await git.commit("auto-signed")
    assert len(await git.head_sha()) == 40
