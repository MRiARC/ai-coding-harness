"""Metrics + health checks + evidence packs (issues 3.11-3.12)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.agents.task import TaskResult
from harness.config import BudgetConfig
from harness.engine.budget import BudgetGovernor
from harness.engine.evidence import EvidencePack, build_summary
from harness.infrastructure.context_store import SQLiteContextStore
from harness.monitoring.health import run_health_checks
from harness.monitoring.metrics import MetricsCollector


@pytest.fixture
def store(tmp_path: Path) -> SQLiteContextStore:
    return SQLiteContextStore(tmp_path / "metrics.db")


def test_metrics_report_shape(store) -> None:
    governor = BudgetGovernor(store, BudgetConfig(total_tokens=10_000), "corr-m")
    metrics = MetricsCollector(store, governor)
    governor.record("impl-1", "model", 200, 50)
    governor.record("impl-1", "model", 100, 25)
    metrics.record_result(TaskResult(task_id="t-1", success=True), agent_id="impl-1")
    metrics.record_result(TaskResult(task_id="t-2", success=False, error="x"), agent_id="impl-1")
    metrics.stage_started("stage-a")
    metrics.stage_finished("stage-a")
    report = metrics.report()
    assert report["tokens_total"] == 375
    assert report["tasks_completed"] == 1 and report["tasks_failed"] == 1
    assert report["per_agent_tokens"]["impl-1"]["total_tokens"] == 375
    assert "stage-a" in report["stage_durations"]
    assert len(report["results"]) == 2
    store.close()


def test_metrics_efficiency_math(store) -> None:
    governor = BudgetGovernor(store, BudgetConfig(total_tokens=10_000), "corr-e")
    metrics = MetricsCollector(store, governor)
    governor.record("a-1", "m", 1000, 0)  # 1k tokens
    metrics.record_result(TaskResult(task_id="t", success=True), agent_id="a-1")
    efficiency = metrics.efficiency()
    assert efficiency["a-1"] == pytest.approx(1.0)  # 1 task per 1k tokens
    store.close()


def test_metrics_stage_without_start(store) -> None:
    governor = BudgetGovernor(store, BudgetConfig(total_tokens=10_000), "corr-s")
    assert MetricsCollector(store, governor).stage_finished("ghost") == 0.0
    store.close()


def test_health_checks_green(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AI_API_KEY", "test-key")
    report = run_health_checks(tmp_path)
    assert report.ready
    names = {c["name"] for c in report.checks}
    assert {"git", "config", "context-store", "results-dir", "api-key"} <= names
    assert "READY: True" in report.summary()


def test_health_reports_missing_key_as_optional(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AI_API_KEY", raising=False)
    report = run_health_checks(tmp_path)
    assert report.ready  # offline mode still ready
    strict = run_health_checks(tmp_path, require_api_key=True)
    assert not strict.ready


def test_health_detects_broken_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AI_API_KEY", raising=False)
    (tmp_path / "harness.yaml").write_text(
        "agents:\n  - agent_id: a\n    role: verifier\n    model: nope\n"
    )
    report = run_health_checks(tmp_path, config_path=tmp_path / "harness.yaml")
    assert not report.ready
    assert any(c["name"] == "config" and not c["ok"] for c in report.checks)


def test_evidence_pack_roundtrip(tmp_path: Path) -> None:
    pack = EvidencePack(tmp_path / "results", "run-abc")
    pack.trace({"event": "run.start", "run_id": "run-abc"})
    pack.trace({"event": "run.end", "run_id": "run-abc", "success": True})
    pack.patch("diff --git a/x b/x")
    pack.test_report("| stage | PASS |")
    pack.token_report({"tokens_total": 42})
    pack.summary(
        build_summary(
            "run-abc",
            "fix the thing",
            "- st-1: do it",
            "| stage | PASS |",
            "VERIFIED: everything",
            ["flag-1"],
        )
    )
    events = pack.read_trace()
    assert len(events) == 2 and events[1]["success"] is True
    assert (pack.path / "patch.diff").exists()
    report = json.loads((pack.path / "token-report.json").read_text())
    assert report["tokens_total"] == 42
    summary = (pack.path / "summary.md").read_text()
    assert "VERIFIED: everything" in summary and "flag-1" in summary


def test_evidence_empty_and_latest(tmp_path: Path) -> None:
    from harness.engine.evidence import latest_evidence

    assert latest_evidence(tmp_path / "results") is None
    (tmp_path / "results").mkdir()
    assert latest_evidence(tmp_path / "results") is None
    pack = EvidencePack(tmp_path / "results", "run-1")
    pack.trace({"event": "x"})
    assert latest_evidence(tmp_path / "results").run_id == "run-1"


def test_format_event_variants() -> None:
    """Pure event renderers moved from the removed cockpit (issue: py-TUI removal)."""
    from harness.engine.evidence import format_event, status_line

    run = {"run_id": "r-1"}
    assert (
        format_event(
            {
                **run,
                "event": "specialist.result",
                "task": "t1",
                "success": True,
                "summary": "did it",
            }
        )
        == "[r-1] t1 -> OK: did it"
    )
    assert (
        format_event({**run, "event": "specialist.assigned", "task": "t1", "agent": "impl-1"})
        == "[r-1] t1 assigned to impl-1"
    )
    assert (
        format_event({**run, "event": "run.end", "success": False}) == "[r-1] run finished: FAILED"
    )
    assert format_event({**run, "event": "other.kind"}) == "[r-1] other.kind"

    # status_line: explicit total wins; per-event sum is the fallback
    events = [
        {**run, "usage": {"total_tokens": 10}},
        {**run, "usage": {"total_tokens": 5}},
    ]
    assert status_line(events, tokens_total=99) == "run: r-1  events: 2  tokens: 99"
    assert status_line(events) == "run: r-1  events: 2  tokens: 15"
    assert status_line([]) == "run: (none)  events: 0  tokens: 0"


def test_adhoc_pack_fallback(tmp_path: Path, monkeypatch) -> None:
    """run's adhoc evidence fallback (no results dir) still constructs a pack."""
    monkeypatch.chdir(tmp_path)
    from harness.cli import _adhoc_pack

    pack = _adhoc_pack()
    assert pack.run_id == "adhoc" and pack.path.is_dir()


def test_latest_evidence_ignores_files(tmp_path: Path) -> None:
    """Non-directory entries under results/ are not runs."""
    from harness.engine.evidence import latest_evidence

    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "stray.txt").write_text("not a run")
    assert latest_evidence(tmp_path / "results") is None


def test_find_evidence_empty_results_dir(tmp_path: Path) -> None:
    """find_evidence with an existing-but-empty results dir returns None."""
    from harness.engine.evidence import find_evidence

    (tmp_path / "results").mkdir()
    assert find_evidence(tmp_path / "results") is None
