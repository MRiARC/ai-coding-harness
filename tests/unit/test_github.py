"""GitHub integration tests: graceful degradation, REST shapes, local git (issue 1.6)."""

from __future__ import annotations

import pytest

from harness.infrastructure.github import GitHubUnavailableError


async def test_offline_service_raises_clearly(github_offline) -> None:
    assert github_offline.available is False
    with pytest.raises(GitHubUnavailableError, match="HARNESS_GITHUB_TOKEN"):
        await github_offline.create_issue("o/r", "t", "b")


async def test_create_issue_request_shape(mock_github) -> None:
    service = mock_github({"/issues": {"number": 7}})
    created = await service.create_issue("o/r", "Fix parser", "broken", labels=["bug"])
    assert created == {"number": 7}
    request = mock_github.captured[-1]  # type: ignore[attr-defined]
    assert request.url.path == "/repos/o/r/issues"
    assert request.headers["Authorization"] == "Bearer test-token"


async def test_pr_lifecycle_endpoints(mock_github) -> None:
    service = mock_github(
        {
            "/pulls": {"number": 1},
            "/merge": {"merged": True},
            "/reviews": {"id": 9},
        }
    )
    await service.create_pull_request("o/r", "t", "head", "main")
    await service.merge_pull_request("o/r", 5, "squash")
    await service.request_changes("o/r", 5, "please fix")
    paths = [r.url.path for r in mock_github.captured]  # type: ignore[attr-defined]
    assert "/repos/o/r/pulls/5/merge" in paths
    assert "/repos/o/r/pulls/5/reviews" in paths


async def test_list_issues_filters_prs(mock_github) -> None:
    service = mock_github(
        {
            "/issues": [
                {"number": 1, "title": "real"},
                {"number": 2, "title": "pr", "pull_request": {"url": "x"}},
            ]
        }
    )
    issues = await service.list_issues("o/r")
    assert [i["number"] for i in issues] == [1]


async def test_pr_status_aggregates_checks(mock_github) -> None:
    service = mock_github(
        {
            "/pulls/5": {"mergeable": True, "state": "open", "head": {"sha": "abc"}},
            "/check-runs": {"check_runs": [{"conclusion": "success"}, {"conclusion": "failure"}]},
        }
    )
    status = await service.pr_status("o/r", 5)
    assert status == {"mergeable": True, "state": "open", "checks_total": 2, "checks_failed": 1}


async def test_git_branch_lifecycle(git_repo) -> None:
    git = git_repo
    await git.init()
    (git.repo_path / "a.txt").write_text("hello\n")
    await git.add("a.txt")
    await git.commit("init")
    await git.create_branch("agent/impl-1/task-1")
    assert await git.current_branch() == "agent/impl-1/task-1"
    assert "agent/impl-1/task-1" in await git.list_branches()
    (git.repo_path / "a.txt").write_text("hello world\n")
    assert "hello world" in await git.diff()
    assert len(await git.head_sha()) == 40
    await git.checkout("main")
    await git.delete_branch("agent/impl-1/task-1", force=True)
    assert "agent/impl-1/task-1" not in await git.list_branches()


async def test_git_failure_raises_giterror(git_repo) -> None:
    from harness.infrastructure.git_local import GitError

    await git_repo.init()
    with pytest.raises(GitError):
        await git_repo.checkout("branch-that-does-not-exist")
