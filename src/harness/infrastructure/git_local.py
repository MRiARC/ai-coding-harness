"""Local git operations (foundation issue 1.6, branch management).

These need no credentials and are the workhorses inside the evaluation
environment: branch-per-subtask, diffs for verification, and commits for the
final patch. All commands run with a timeout and never leak to a shell.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from harness.infrastructure.logging import get_logger

logger = get_logger(__name__)

GIT_TIMEOUT_SECONDS = 120.0


class GitError(RuntimeError):
    """A git command failed; message carries git's stderr."""


class GitService:
    """Thin, safe wrapper over the `git` CLI for one working repository."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path).resolve()

    async def _run(self, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=self.repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), GIT_TIMEOUT_SECONDS)
        except TimeoutError:
            proc.kill()
            msg = f"git {' '.join(args[:3])}... timed out after {GIT_TIMEOUT_SECONDS}s"
            raise GitError(msg) from None
        if proc.returncode != 0:
            msg = f"git {' '.join(args)} failed: {stderr.decode().strip()[:300]}"
            raise GitError(msg)
        return stdout.decode()

    async def init(self, default_branch: str = "main") -> None:
        await self._run("init", "-b", default_branch)

    async def clone(self, url: str, depth: int = 1) -> None:
        await self._run("clone", "--depth", str(depth), url, str(self.repo_path))

    async def create_branch(self, name: str, from_ref: str = "HEAD") -> None:
        await self._run("checkout", "-b", name, from_ref)
        logger.info("branch created", branch=name, repo=str(self.repo_path))

    async def checkout(self, ref: str) -> None:
        await self._run("checkout", ref)

    async def delete_branch(self, name: str, force: bool = False) -> None:
        await self._run("branch", "-D" if force else "-d", name)

    async def list_branches(self) -> list[str]:
        out = await self._run("branch", "--format=%(refname:short)")
        return [line.strip() for line in out.splitlines() if line.strip()]

    async def current_branch(self) -> str:
        return (await self._run("rev-parse", "--abbrev-ref", "HEAD")).strip()

    async def status(self) -> str:
        return (await self._run("status", "--porcelain")).strip()

    async def diff(self, ref: str = "HEAD") -> str:
        """Unified diff of the working tree (or against `ref`)."""
        return await self._run("diff", ref) if ref != "WORKING" else await self._run("diff")

    async def add(self, *paths: str) -> None:
        await self._run("add", "--", *paths) if paths else await self._run("add", "-A")

    async def commit(self, message: str) -> str:
        out = await self._run("commit", "-m", message)
        logger.info("commit created", repo=str(self.repo_path), message=message[:80])
        return out

    async def head_sha(self) -> str:
        return (await self._run("rev-parse", "HEAD")).strip()
