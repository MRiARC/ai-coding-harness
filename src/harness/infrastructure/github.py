"""GitHub REST integration (foundation issue 1.6).

Uses httpx directly against the REST API - no PyGithub dependency. The token
is discovered from an explicit argument, then `HARNESS_GITHUB_TOKEN` /
`GITHUB_TOKEN`, then `gh auth token` (the CLI's stored credentials). When no
credential exists - the normal case in the evaluation environment, which only
guarantees `AI_API_KEY` - every network method raises `GitHubUnavailableError`
with a clear message instead of failing mysteriously mid-run.

Local repository operations (branch, diff, commit) live in `git_local.py` and
need no token at all.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any

import httpx

from harness.infrastructure.logging import get_logger

logger = get_logger(__name__)

DEFAULT_API_URL = "https://api.github.com"
TOKEN_ENV_VARS = ("HARNESS_GITHUB_TOKEN", "GITHUB_TOKEN")


class GitHubUnavailableError(RuntimeError):
    """Raised when GitHub credentials are missing or the API is unreachable."""


def discover_token() -> str | None:
    """Explicit env vars first, then the `gh` CLI's stored credentials."""
    for env in TOKEN_ENV_VARS:
        if token := os.environ.get(env):
            return token
    if shutil.which("gh"):
        try:
            result = asyncio.run(_gh_token())
        except Exception:  # pragma: no cover - gh presence != gh auth
            return None
        if result:
            return result
    return None


async def _gh_token() -> str | None:
    proc = await asyncio.create_subprocess_exec(
        "gh",
        "auth",
        "token",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()
    token = stdout.decode().strip()
    return token or None


class GitHubService:
    """Async GitHub REST client with graceful unavailability."""

    def __init__(
        self,
        token: str | None = None,
        api_url: str = DEFAULT_API_URL,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token = token if token is not None else discover_token()
        self._api_url = api_url.rstrip("/")
        self._client = client

    @property
    def available(self) -> bool:
        """Whether authenticated GitHub operations can proceed.

        An explicitly-passed empty token counts as unavailable: that is how
        tests (and cautious callers) force the offline path.
        """
        return bool(self._token)

    def _require_token(self) -> str:
        if not self._token:
            msg = (
                "GitHub credentials not found; set HARNESS_GITHUB_TOKEN or GITHUB_TOKEN, "
                "or authenticate with `gh auth login`. Local git operations do not need this."
            )
            raise GitHubUnavailableError(msg)
        return self._token

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._api_url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        token = self._require_token()
        response = await self._http().request(
            method,
            path,
            json=json_body,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code >= 400:
            msg = f"GitHub {method} {path} -> HTTP {response.status_code}: {response.text[:300]}"
            raise RuntimeError(msg)
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    # -- issues & PRs --------------------------------------------------------
    async def create_issue(
        self, repo: str, title: str, body: str, labels: list[str] | None = None
    ) -> dict[str, Any]:
        """Open an issue in `owner/name`."""
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        result = await self._request("POST", f"/repos/{repo}/issues", json_body=payload)
        return result

    async def add_comment(self, repo: str, issue_number: int, body: str) -> dict[str, Any]:
        """Comment on an issue or PR (same endpoint)."""
        result = await self._request(
            "POST", f"/repos/{repo}/issues/{issue_number}/comments", json_body={"body": body}
        )
        return result

    async def create_pull_request(
        self, repo: str, title: str, head: str, base: str, body: str = ""
    ) -> dict[str, Any]:
        result = await self._request(
            "POST",
            f"/repos/{repo}/pulls",
            json_body={"title": title, "head": head, "base": base, "body": body},
        )
        return result

    async def merge_pull_request(
        self, repo: str, pr_number: int, merge_method: str = "merge"
    ) -> dict[str, Any]:
        result = await self._request(
            "PUT",
            f"/repos/{repo}/pulls/{pr_number}/merge",
            json_body={"merge_method": merge_method},
        )
        return result

    async def request_changes(self, repo: str, pr_number: int, body: str) -> dict[str, Any]:
        """Submit a REQUEST_CHANGES review (the review-agent's signature move)."""
        result = await self._request(
            "POST",
            f"/repos/{repo}/pulls/{pr_number}/reviews",
            json_body={"event": "REQUEST_CHANGES", "body": body},
        )
        return result

    async def list_issues(
        self, repo: str, state: str = "open", limit: int = 50
    ) -> list[dict[str, Any]]:
        result = await self._request(
            "GET", f"/repos/{repo}/issues", params={"state": state, "per_page": limit}
        )
        rows = result if isinstance(result, list) else []
        return [item for item in rows if isinstance(item, dict) and "pull_request" not in item]

    async def list_pull_requests(
        self, repo: str, state: str = "open", limit: int = 50
    ) -> list[dict[str, Any]]:
        result = await self._request(
            "GET", f"/repos/{repo}/pulls", params={"state": state, "per_page": limit}
        )
        return result if isinstance(result, list) else []

    async def pr_status(self, repo: str, pr_number: int) -> dict[str, Any]:
        """Aggregate mergeability + CI check summary for a PR."""
        pr = await self._request("GET", f"/repos/{repo}/pulls/{pr_number}")
        sha = pr.get("head", {}).get("sha", "")
        checks = await self._request("GET", f"/repos/{repo}/commits/{sha}/check-runs")
        check_runs = checks.get("check_runs", []) if isinstance(checks, dict) else []
        return {
            "mergeable": pr.get("mergeable"),
            "state": pr.get("state"),
            "checks_total": len(check_runs),
            "checks_failed": sum(1 for c in check_runs if c.get("conclusion") == "failure"),
        }

    # -- repository cloning ----------------------------------------------------
    async def clone(self, url: str, destination: Path) -> Path:
        """Clone a repository (public repos need no token)."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        proc = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            "--depth",
            "1",
            url,
            str(destination),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            msg = f"git clone {url} failed: {stderr.decode().strip()[:300]}"
            raise RuntimeError(msg)
        logger.info("repository cloned", url=url, destination=str(destination))
        return destination

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
