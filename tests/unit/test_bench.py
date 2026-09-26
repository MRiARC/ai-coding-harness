"""Tests for the A/B token benchmark (milestone 5, issue 5.5).

The subprocess-backed measurements run the real pipeline offline; everything
else (compare math, table rendering, CLI flow) is pure and fast.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from harness.bench import tokens as bench_tokens
from harness.bench.runner import build_fixture, run_once
from harness.bench.runner import main as runner_main


def test_build_fixture_creates_git_repo(tmp_path: Path) -> None:
    root = build_fixture(tmp_path / "fixture")
    assert (root / "app.py").exists()
    assert (root / "test_greet.py").exists()
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    assert len(proc.stdout.strip()) == 40


async def test_run_once_returns_token_report(tmp_path: Path) -> None:
    fixture = build_fixture(tmp_path / "fixture")
    result = await run_once(fixture, tmp_path / "results", "app.greet() should return hello")
    assert result["success"], result["outcome_line"]
    report = result["token_report"]
    assert report["tokens_total"] > 0
    assert "arch-1" in report["per_agent_tokens"]
    assert "ver-1" in report["per_agent_tokens"]
    assert report["tasks_completed"] == 1


def test_run_measurement_deterministic() -> None:
    first = bench_tokens.run_measurement(None)
    second = bench_tokens.run_measurement(None)
    assert first["success"] and second["success"]
    key_fields = ("per_agent_tokens", "tokens_total", "tasks_completed")
    for field in key_fields:
        assert first["token_report"][field] == second["token_report"][field], field


def test_runner_main_prints_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = runner_main(["--fixture-dir", str(tmp_path / "fx"), "--work-dir", str(tmp_path / "w")])
    assert code == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    payload = json.loads(lines[-1])
    assert payload["success"] is True
    assert payload["token_report"]["tokens_total"] > 0


def test_runner_main_failure_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pipeline that reports failure makes the runner exit 1."""

    async def failing_run_once(fixture: Path, results_dir: Path, issue: str) -> dict[str, Any]:
        return {
            "success": False,
            "outcome_line": "NOT VERIFIED (forced)",
            "run_id": "x",
            "token_report": {},
        }

    monkeypatch.setattr("harness.bench.runner.run_once", failing_run_once)
    assert runner_main(["--fixture-dir", str(tmp_path / "fx"), "--work-dir", str(tmp_path)]) == 1


async def test_run_once_missing_token_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pipeline outcome without an evidence pack degrades to an empty report."""

    class FakePipeline:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        async def run(self, issue: str, demo_mode: bool = False) -> Any:
            return SimpleNamespace(
                success=False,
                outcome_line="FAILED: forced",
                run_id="forced",
                evidence_path=None,
            )

    monkeypatch.setattr("harness.engine.pipeline.HarnessPipeline", FakePipeline)
    fixture = build_fixture(tmp_path / "fixture")
    result = await run_once(fixture, tmp_path / "results", "issue")
    assert result["success"] is False
    assert result["token_report"] == {}


def test_compare_math() -> None:
    baseline = {
        "token_report": {
            "tokens_total": 1000,
            "tasks_completed": 1,
            "per_agent_tokens": {
                "arch-1": {"prompt_tokens": 800, "completion_tokens": 200, "total_tokens": 1000}
            },
        }
    }
    candidate = {
        "token_report": {
            "tokens_total": 500,
            "tasks_completed": 1,
            "per_agent_tokens": {
                "arch-1": {"prompt_tokens": 400, "completion_tokens": 100, "total_tokens": 500},
                "ver-1": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        }
    }
    delta = bench_tokens.compare(baseline, candidate)
    arch = delta["per_agent"]["arch-1"]["total_tokens"]
    assert arch == {"baseline": 1000, "candidate": 500, "delta": -500, "pct": -50.0}
    new_agent = delta["per_agent"]["ver-1"]["total_tokens"]
    assert new_agent == {"baseline": 0, "candidate": 0, "delta": 0, "pct": None}
    total = delta["totals"]["tokens_total"]
    assert total == {"baseline": 1000, "candidate": 500, "delta": -500, "pct": -50.0}


def test_render_table() -> None:
    delta = bench_tokens.compare(
        {"token_report": {"tokens_total": 100, "tasks_completed": 1, "per_agent_tokens": {}}},
        {"token_report": {"tokens_total": 50, "tasks_completed": 1, "per_agent_tokens": {}}},
    )
    table = bench_tokens.render_table(delta)
    assert "agent/metric" in table
    assert "TOTAL tokens_total" in table
    assert "-50.0%" in table
    assert "-50" in table


def test_main_without_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # no docs/evidence/bench-baseline.json here
    code = bench_tokens.main(["--baseline-path", str(tmp_path / "absent.json")])
    out = capsys.readouterr().out
    assert code == 0
    assert "no baseline" in out
    assert "tokens_total" in out


def test_main_compare_with_saved_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = bench_tokens.run_measurement(None)
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    code = bench_tokens.main(
        ["--baseline-path", str(baseline_path), "--json-out", str(tmp_path / "delta.json")]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "+0.0%" in out
    payload = json.loads((tmp_path / "delta.json").read_text(encoding="utf-8"))
    assert payload["delta"]["totals"]["tokens_total"]["delta"] == 0


def test_main_ref_ab(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Full A/B against a git ref: detached worktree, measured, cleaned up."""
    code = bench_tokens.main(["--ref", "HEAD", "--json-out", str(tmp_path / "ab.json")])
    out = capsys.readouterr().out
    assert code == 0
    assert "TOTAL tokens_total" in out
    payload = json.loads((tmp_path / "ab.json").read_text(encoding="utf-8"))
    assert payload["delta"]["totals"]["tokens_total"]["delta"] == 0
    worktrees = subprocess.run(
        ["git", "worktree", "list"], capture_output=True, text=True, check=True
    ).stdout
    assert "harness-bench-ref-" not in worktrees


def test_main_bad_ref_fails_fast(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # not a git repo: worktree add fails immediately
    with pytest.raises(RuntimeError, match="cannot create worktree"):
        bench_tokens.main(["--ref", "no-such-ref"])


def test_main_candidate_failure(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        bench_tokens,
        "run_measurement",
        lambda *_a, **_k: {"success": False, "outcome_line": "NOT VERIFIED", "token_report": {}},
    )
    assert bench_tokens.main([]) == 1
    assert "did not reach VERIFIED" in capsys.readouterr().out


def test_main_saves_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    canned = {
        "success": True,
        "outcome_line": "VERIFIED",
        "run_id": "canned",
        "token_report": {"tokens_total": 42, "per_agent_tokens": {}},
    }
    monkeypatch.setattr(bench_tokens, "run_measurement", lambda *_a, **_k: canned)
    baseline_path = tmp_path / "saved" / "baseline.json"
    code = bench_tokens.main(["--save-baseline", "--baseline-path", str(baseline_path)])
    assert code == 0
    saved = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert saved["token_report"]["tokens_total"] == 42


def test_cli_bench_command(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`harness bench` CLI wiring forwards flags into the bench main."""
    from harness import cli

    seen: dict[str, Any] = {}

    def fake_main(argv: list[str]) -> int:
        seen["argv"] = argv
        return 0

    monkeypatch.setattr("harness.bench.tokens.main", fake_main)
    code = cli.main(
        [
            "bench",
            "--ref",
            "HEAD",
            "--save-baseline",
            "--json-out",
            "d.json",
            "--issue",
            "i",
            "--baseline-path",
            "b.json",
        ]
    )
    assert code == 0
    assert seen["argv"] == [
        "--issue",
        "i",
        "--ref",
        "HEAD",
        "--save-baseline",
        "--baseline-path",
        "b.json",
        "--json-out",
        "d.json",
    ]


def test_fixture_root_default_and_rebuild() -> None:
    """build_fixture() with no args uses the canonical path and replaces it."""
    first = build_fixture()
    assert first.name == "harness-bench-fixture"
    second = build_fixture()  # exists-branch: rmtree + recreate
    assert second == first
    assert (second / "app.py").exists()


def test_run_measurement_runner_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(bench_tokens.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="bench runner failed"):
        bench_tokens.run_measurement(None)


def test_run_measurement_no_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(returncode=0, stdout="\n  \n", stderr="")

    monkeypatch.setattr(bench_tokens.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="no output"):
        bench_tokens.run_measurement(None)
