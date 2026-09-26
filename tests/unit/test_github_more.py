"""Extended GitHub tests: token discovery, clone, edge paths (issue 1.6)."""

from __future__ import annotations

import httpx
import pytest

from harness.infrastructure import github as github_module
from harness.infrastructure.github import GitHubService


def test_discover_token_from_env(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_GITHUB_TOKEN", "env-token")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert github_module.discover_token() == "env-token"


def test_discover_token_prefers_explicit_env_over_github_token(monkeypatch) -> None:
    monkeypatch.setenv("HARNESS_GITHUB_TOKEN", "first")
    monkeypatch.setenv("GITHUB_TOKEN", "second")
    assert github_module.discover_token() == "first"


def test_discover_token_via_gh_cli(monkeypatch) -> None:
    for var in ("HARNESS_GITHUB_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(github_module.shutil, "which", lambda name: "/usr/bin/gh")

    async def fake_gh_token() -> str | None:
        return "gh-stored-token"

    monkeypatch.setattr(github_module, "_gh_token", fake_gh_token)
    assert github_module.discover_token() == "gh-stored-token"


def test_discover_token_absent(monkeypatch) -> None:
    for var in ("HARNESS_GITHUB_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(github_module.shutil, "which", lambda name: None)
    assert github_module.discover_token() is None


async def test_empty_body_response_returns_dict() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    service = GitHubService(
        token="t",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        ),
    )
    assert await service.merge_pull_request("o/r", 1) == {}
    await service.aclose()


async def test_reused_client_serves_multiple_requests() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"n": 1})

    service = GitHubService(
        token="t",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        ),
    )
    await service.add_comment("o/r", 1, "one")
    await service.add_comment("o/r", 1, "two")
    await service.aclose()  # closes the underlying client; second close is safe
    await service.aclose()


async def test_list_pull_requests_non_list_response_narrowed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    service = GitHubService(
        token="t",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        ),
    )
    assert await service.list_pull_requests("o/r") == []
    await service.aclose()


async def test_create_issue_without_labels_omits_field(mock_github) -> None:
    service = mock_github({"/issues": {"number": 1}})
    await service.create_issue("o/r", "t", "b")
    request = mock_github.captured[-1]  # type: ignore[attr-defined]
    import json

    body = json.loads(request.content)
    assert "labels" not in body


async def test_clone_local_repository(tmp_path) -> None:
    import subprocess

    source = tmp_path / "src-repo"
    source.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(source)], check=True)
    (source / "f.txt").write_text("data\n")
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

    service = GitHubService(token="", client=httpx.AsyncClient())  # clone needs no token
    destination = await service.clone(str(source), tmp_path / "clone")
    assert (destination / "f.txt").exists()


async def test_clone_failure_raises(tmp_path) -> None:
    service = GitHubService(token="", client=httpx.AsyncClient())
    with pytest.raises(RuntimeError, match="git clone"):
        await service.clone(str(tmp_path / "does-not-exist"), tmp_path / "dest")


class _FakeProc:
    def __init__(self, stdout: bytes) -> None:
        self._stdout = stdout

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, b""


async def test_gh_cli_token_capture(monkeypatch) -> None:
    async def fake_exec(*args, **kwargs):
        return _FakeProc(b"  gh-token-123\n")

    monkeypatch.setattr(github_module.asyncio, "create_subprocess_exec", fake_exec)
    assert await github_module._gh_token() == "gh-token-123"


async def test_gh_cli_token_empty_output(monkeypatch) -> None:
    async def fake_exec(*args, **kwargs):
        return _FakeProc(b"")

    monkeypatch.setattr(github_module.asyncio, "create_subprocess_exec", fake_exec)
    assert await github_module._gh_token() is None


async def test_default_client_is_built_lazily(monkeypatch) -> None:
    """No injected client: the service constructs its own on first request."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.github.com"
        return httpx.Response(200, json={"n": 1})

    fake_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.github.com"
    )
    monkeypatch.setattr(github_module.httpx, "AsyncClient", lambda **kwargs: fake_client)
    service = GitHubService(token="t")  # no client injected
    result = await service.add_comment("o/r", 1, "hello")
    assert result == {"n": 1}
    await service.aclose()


async def test_http_error_response_raises_runtimeerror() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "boom"})

    service = GitHubService(
        token="t",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        ),
    )
    with pytest.raises(RuntimeError, match="HTTP 500"):
        await service.list_issues("o/r")
    await service.aclose()
