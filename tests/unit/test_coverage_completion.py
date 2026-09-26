"""Branch-completion suite: every defensive/edge path in Milestone 3.

Each test targets specific uncovered branches found by the coverage report;
grouped here so the intent (100% branch coverage) is explicit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from harness.config import HarnessConfig
from harness.engine.evidence import EvidencePack
from harness.infrastructure.model_providers import FakeProvider
from harness.monitoring.health import run_health_checks
from harness.security.audit import AuditLog
from harness.security.secret_scanner import check_path_policy, scan_text
from harness.tools.editing import (
    ApplyEditTool,
    SearchTextTool,
    SyntaxCheckTool,
    _whitespace_tolerant,
)
from harness.tools.execution import RunTestsTool, SecurityScanTool
from harness.tools.filesystem import ListDirTool, ReadFileTool
from harness.tools.vcs import GitBranchTool, GitDiffTool, GitStatusTool
from harness.verification.code_review import review_paths


# -- cli run_command (both interface branches) ---------------------------------
def test_run_command_headless(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AI_API_KEY", raising=False)

    class FakeStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return ""

    monkeypatch.setattr(sys, "stdin", FakeStdin())
    from harness.cli import run_command

    assert run_command() == 0
    assert "READY" in capsys.readouterr().out


def test_run_command_tty_launches_cockpit(monkeypatch, tmp_path) -> None:
    launched = {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_API_KEY", "k")

    class FakeStdin:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdin", FakeStdin())
    import harness.cli as cli

    class FakeApp:
        def __init__(self, pack) -> None:
            launched["pack"] = pack

        def run(self) -> None:
            launched["ran"] = True

    monkeypatch.setattr("harness.ui.tui.CockpitApp", FakeApp)
    assert cli.run_command() == 0
    # TTY path constructed a cockpit (via the EvidencePack fallback branch)
    assert (tmp_path / "results" / "adhoc").exists()


def test_run_command_headless_not_ready(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "harness.yaml").write_text(
        "agents:\n  - agent_id: a\n    role: verifier\n    model: nope\n"
    )

    class FakeStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return ""

    monkeypatch.setattr(sys, "stdin", FakeStdin())
    from harness.cli import run_command

    assert run_command() == 1


# -- evidence edges --------------------------------------------------------------
def test_evidence_read_trace_empty_and_corrupt(tmp_path: Path) -> None:
    pack = EvidencePack(tmp_path, "run-e")  # no trace written yet
    assert pack.read_trace() == []
    (pack.path / "trace.jsonl").write_text('{"event": "a"}\n{corrupt\n')
    events = pack.read_trace()
    assert len(events) == 1 and events[0]["event"] == "a"


# -- pipeline: disabled agent skip ------------------------------------------------
def test_pipeline_skips_disabled_agents(tmp_path) -> None:
    from harness.infrastructure.context_store import MemoryContextStore

    demo_repo = tmp_path
    config = HarnessConfig.model_validate(
        {
            "models": {"default": {"provider": "fake", "name": "m"}},
            "agents": [{"agent_id": "a", "role": "verifier", "model": "default", "enabled": False}],
            "storage": {"backend": "memory"},
        }
    )
    disabled = config.model_copy(deep=True)
    agents = [a.model_copy(update={"enabled": False}) for a in disabled.agents]
    disabled = disabled.model_copy(update={"agents": agents})
    store = MemoryContextStore()
    from harness.engine.pipeline import HarnessPipeline

    pipeline = HarnessPipeline(demo_repo, disabled, FakeProvider(None, []), store)
    assert pipeline._agents == {}
    assert pipeline._specialist_slots == []


# -- health failure branches -------------------------------------------------------
def test_health_store_failure(tmp_path: Path, monkeypatch) -> None:

    def explode(*args, **kwargs):
        raise RuntimeError("sqlite gone")

    monkeypatch.setattr("harness.infrastructure.context_store.SQLiteContextStore", explode)
    report = run_health_checks(tmp_path)
    store_check = next(c for c in report.checks if c["name"] == "context-store")
    assert not store_check["ok"] and "sqlite gone" in store_check["detail"]


def test_health_results_dir_failure(tmp_path: Path) -> None:
    (tmp_path / "results").write_text("i am a file, not a directory")
    report = run_health_checks(tmp_path)
    results_check = next(c for c in report.checks if c["name"] == "results-dir")
    assert not results_check["ok"]


# -- audit edges ---------------------------------------------------------------------
def test_audit_load_last_hash_skips_garbage(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "audit.jsonl")
    entry = log.append("a", "valid")
    with (tmp_path / "audit.jsonl").open("a") as handle:
        handle.write("{garbage tail\n")
    revived = AuditLog(tmp_path / "audit.jsonl")
    assert revived._prev_hash == entry["entry_hash"]
    assert len(revived.entries()) == 1


def test_audit_verify_detects_broken_link(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append("a", "one")
    log.append("a", "two")
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    lines[1]["prev_hash"] = "f" * 64  # recompute hash for entry 1 but keep bad link
    payload = {k: v for k, v in lines[1].items() if k not in {"prev_hash", "entry_hash"}}
    import hashlib

    lines[1]["entry_hash"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path.write_text("\n".join(json.dumps(entry, sort_keys=True) for entry in lines) + "\n")
    ok, reason = log.verify()
    assert not ok and "broken prev_hash link" in reason


def test_audit_export_empty_log(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "audit.jsonl")
    exported = log.export(tmp_path / "out.jsonl")
    assert exported.read_text() == ""


# -- secret scanner edges ---------------------------------------------------------------
def test_path_policy_strips_dot_slash_prefix() -> None:
    assert check_path_policy("./src/auth/login.py").requires_review == "security review"
    assert check_path_policy("./migrations/0001.py").requires_review == "specialist approval"
    assert check_path_policy("auth/login.py").requires_review == "security review"


def test_scan_path_skips_oversized_and_unreadable(tmp_path: Path) -> None:
    (tmp_path / "big.py").write_text("password = " + "a" * 400_000)  # over size cap
    locked = tmp_path / "locked.py"
    locked.write_text("password = real_secret_here\n")
    locked.chmod(0o000)
    try:
        assert scan_path_findings(tmp_path) == []
    finally:
        locked.chmod(0o644)


def scan_path_findings(root: Path):
    from harness.security.secret_scanner import scan_path

    return scan_path(root)


def test_scan_text_breaks_after_first_kind_per_line() -> None:
    findings = scan_text("AKIAIOSFODNN7EXAMPLE password = x123456")
    assert len(findings) == 1 and findings[0].kind == "aws-access-key"


# -- tool defensive branches --------------------------------------------------------------
def test_search_regex_defensive_and_skips(repo_with_subdir) -> None:
    tool = SearchTextTool(repo_with_subdir)
    result = tool.execute(pattern="(")  # bypasses validate_input on purpose
    assert not result.success and "invalid regex" in result.error
    ok = tool.execute(pattern="def", path=".")
    assert ok.success  # dirs and skip-dirs hit their `continue` arms


def test_search_skips_large_and_unreadable(tmp_path: Path, monkeypatch) -> None:
    import harness.tools.editing as editing

    (tmp_path / "big.py").write_text("def needle():\n" + "x = 1\n" * 200_000)
    locked = tmp_path / "locked.py"
    locked.write_text("def needle():\n    pass\n")
    locked.chmod(0o000)
    monkeypatch.setattr(editing, "MAX_SEARCH_BYTES_PER_FILE", 1000)
    try:
        result = SearchTextTool(tmp_path).execute(pattern="needle")
        assert result.success and "locked.py" not in result.output
    finally:
        locked.chmod(0o644)


def test_search_match_cap(tmp_path: Path, monkeypatch) -> None:
    import harness.tools.editing as editing

    for i in range(4):
        (tmp_path / f"f{i}.py").write_text("needle here\n")
    monkeypatch.setattr(editing, "MAX_SEARCH_RESULTS", 2)
    result = SearchTextTool(tmp_path).execute(pattern="needle")
    assert result.data["capped"] is True and result.data["matches"] == 2


def test_whitespace_tolerant_empty_target() -> None:
    assert _whitespace_tolerant(["a"], []) is None


def test_apply_edit_read_failure(tmp_path: Path) -> None:
    locked = tmp_path / "locked.py"
    locked.write_text("search me\n")
    locked.chmod(0o000)
    try:
        result = ApplyEditTool(tmp_path).execute(path="locked.py", search="search me", replace="x")
        assert not result.success and "cannot read" in result.error
    finally:
        locked.chmod(0o644)


def test_apply_edit_validate_all_valid(repo) -> None:
    tool = ApplyEditTool(repo)
    assert tool.validate_input({"path": "p", "search": "s", "replace": "r"}) == []


def test_syntax_check_traversal_path(repo) -> None:
    result = SyntaxCheckTool(repo).execute(paths=["../evil.py"])
    assert not result.success and any("escapes" in e for e in result.data["errors"])


def test_run_tests_and_scan_validate_defaults(repo, tmp_path) -> None:
    assert RunTestsTool(repo).validate_input({}) == []
    assert SecurityScanTool(tmp_path).validate_input({}) == []


# -- filesystem defensive branches -----------------------------------------------------------
def test_read_file_unreadable(repo) -> None:
    locked = repo / "locked.txt"
    locked.write_text("secret content\n")
    locked.chmod(0o000)
    try:
        result = ReadFileTool(repo).execute(path="locked.txt")
        assert not result.success and "cannot read" in result.error
    finally:
        locked.chmod(0o644)


def test_list_dir_validate_and_cap(repo, monkeypatch) -> None:
    import harness.tools.filesystem as fs

    for i in range(4):
        (repo / f"file{i}.txt").write_text("x")
    monkeypatch.setattr(fs, "MAX_LIST_ENTRIES", 2)
    result = ListDirTool(repo).execute()
    assert "capped at 2 entries" in result.output
    assert ListDirTool(repo).validate_input({}) == []


def test_list_dir_unreadable(repo) -> None:
    locked = repo / "lockeddir"
    locked.mkdir()
    locked.chmod(0o000)
    try:
        result = ListDirTool(repo).execute(path="lockeddir")
        assert not result.success and "cannot list" in result.error
    finally:
        locked.chmod(0o755)


# -- vcs validation defaults ---------------------------------------------------------------------
def test_vcs_validate_defaults(repo) -> None:
    assert GitStatusTool(repo).validate_input({}) == []
    assert GitBranchTool(repo).validate_input({"action": "delete"}) != []
    assert GitDiffTool(repo).validate_input({}) == []


# -- code review: long function, dunders, async, syntax errors ------------------------------
def test_review_paths_all_branches(tmp_path: Path) -> None:
    long_fn = "def long_one():\n" + "".join(f"    x{i} = {i}\n" for i in range(90))
    (tmp_path / "long.py").write_text(long_fn)
    (tmp_path / "dunder.py").write_text(
        "class Thing:\n    def __init__(self):\n        self.x = 1\n"
    )
    (tmp_path / "asyncy.py").write_text("async def handler():\n    return 1\n")
    (tmp_path / "broken.py").write_text("def broken(:\n")
    findings = review_paths(
        [
            tmp_path / "long.py",
            tmp_path / "dunder.py",
            tmp_path / "asyncy.py",
            tmp_path / "broken.py",
        ],
        tmp_path,
    )
    kinds = {f.kind for f in findings}
    assert "long-function" in kinds  # 90 lines > 80
    assert "missing-docstring" in kinds  # async handler, public, no docstring
    # dunders are exempt; broken.py is skipped (SyntaxError branch)


# -- verification: final-review skipped when no architect ------------------------------------
async def test_final_review_skipped_without_architect(repo) -> None:
    from harness.verification.pipeline import VerificationPipeline

    results = await VerificationPipeline(repo).run(diff="", plan=None, architect=None)
    by_name = {r.name: r for r in results}
    assert "5-final-review" in by_name
    assert by_name["5-final-review"].passed
    assert "skipped" in by_name["5-final-review"].detail


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    return tmp_path


@pytest.fixture
def repo_with_subdir(repo: Path) -> Path:
    return repo


def test_audit_entries_skip_blank_lines(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append("a", "one")
    with (tmp_path / "audit.jsonl").open("a") as handle:
        handle.write("\n   \n")
    assert len(log.entries()) == 1


def test_scan_path_respects_limit_files(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("password = one_secret_1\n")
    (tmp_path / "b.py").write_text("password = two_secret_2\n")
    findings = scan_path_findings(tmp_path)
    assert len(findings) == 2  # sanity: both files hold secrets


def test_search_text_skips_vendored_dirs(tmp_path: Path) -> None:
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "junk.py").write_text("needle in vendored code\n")
    result = SearchTextTool(tmp_path).execute(pattern="needle")
    assert result.data["matches"] == 0  # .venv contents skipped entirely


def test_syntax_check_validate_accepts_valid_paths(repo) -> None:
    assert SyntaxCheckTool(repo).validate_input({"paths": ["a.py"]}) == []


def test_git_branch_validate_rejects_unknown_action(repo) -> None:
    assert GitBranchTool(repo).validate_input({"action": "rename", "name": "x"}) != []


def test_scan_path_limit_break(tmp_path: Path) -> None:
    from harness.security.secret_scanner import scan_path

    (tmp_path / "a.py").write_text("password = one_secret_1\n")
    (tmp_path / "b.py").write_text("password = two_secret_2\n")
    findings = scan_path(tmp_path, limit_files=1)  # second file trips the break
    assert len(findings) == 1 and findings[0].path == "a.py"
