"""Cockpit logic tests — pure functions only (Textual lifecycle excluded).

The App lifecycle is `# pragma: no cover` and exercised manually: Textual's
headless `run_test()` hangs under some platform/pytest combinations, so the
suite covers the rendering logic without booting the event loop.
"""

from __future__ import annotations

from pathlib import Path

from harness.engine.evidence import EvidencePack
from harness.ui.tui import CockpitApp, format_event, latest_evidence, status_line


def test_format_event_variants() -> None:
    assert format_event({"event": "run.start", "run_id": "r1"}) == "[r1] run.start"
    assert (
        format_event(
            {"event": "specialist.assigned", "run_id": "r1", "task": "st-1", "agent": "ver-1"}
        )
        == "[r1] st-1 assigned to ver-1"
    )
    ok = format_event(
        {
            "event": "specialist.result",
            "run_id": "r1",
            "task": "st-1",
            "success": True,
            "summary": "greet works",
        }
    )
    assert ok == "[r1] st-1 -> OK: greet works"
    fail = format_event(
        {
            "event": "specialist.result",
            "run_id": "r1",
            "task": "st-2",
            "success": False,
            "summary": "regression",
        }
    )
    assert "FAIL: regression" in fail
    assert (
        format_event({"event": "run.end", "run_id": "r1", "success": True})
        == "[r1] run finished: SUCCESS"
    )
    assert format_event({"event": "run.end", "run_id": "r1"}) == "[r1] run finished: FAILED"
    assert format_event({"event": "mystery"}) == "[-] mystery"


def test_status_line_counts_tokens() -> None:
    events = [
        {"run_id": "r1", "usage": {"total_tokens": 100}},
        {"run_id": "r1"},
        {"run_id": "r1", "usage": {"total_tokens": 21}},
    ]
    assert status_line(events) == "run: r1  events: 3  tokens: 121"
    assert status_line([]) == "run: (none)  events: 0  tokens: 0"


def test_latest_evidence_picks_recent(tmp_path: Path) -> None:
    import os
    import time

    assert latest_evidence(tmp_path / "results") is None
    (tmp_path / "results").mkdir()
    assert latest_evidence(tmp_path / "results") is None
    old = EvidencePack(tmp_path / "results", "run-old")
    old.trace({"event": "x"})
    os.utime(old.path, (time.time() - 100, time.time() - 100))
    new = EvidencePack(tmp_path / "results", "run-new")
    new.trace({"event": "y"})
    assert latest_evidence(tmp_path / "results").run_id == "run-new"


def test_status_line_prefers_token_report_total() -> None:
    events = [{"run_id": "r1", "usage": {"total_tokens": 7}}]
    assert "tokens: 112229" in status_line(events, tokens_total=112229)
    assert "tokens: 7" in status_line(events)  # fallback: per-event sum


def test_cockpit_reads_tokens_from_pack_report(tmp_path: Path) -> None:
    """The meter uses token-report.json (authoritative), not event sums."""
    from harness.ui.tui import CockpitApp

    pack = EvidencePack(tmp_path / "results", "run-tok")
    pack.trace({"event": "run.start", "run_id": "run-tok"})
    pack.token_report({"tokens_total": 112229})
    app = CockpitApp(pack)
    app.refresh_trace() if False else None
    # _tokens_from_report is lifecycle-free: call it directly
    assert app._tokens_from_report() == 112229
    empty = CockpitApp(EvidencePack(tmp_path / "results", "run-empty"))
    assert empty._tokens_from_report() is None
    assert CockpitApp(None)._tokens_from_report() is None


def test_cockpit_tolerates_corrupt_token_report(tmp_path: Path) -> None:
    from harness.ui.tui import CockpitApp

    pack = EvidencePack(tmp_path / "results", "run-bad")
    (pack.path / "token-report.json").write_text("{corrupt")
    assert CockpitApp(pack)._tokens_from_report() is None


def test_cockpit_renders_report_tokens_in_status(tmp_path: Path) -> None:
    pack = EvidencePack(tmp_path / "results", "run-tok2")
    pack.trace({"event": "run.start", "run_id": "run-tok2"})
    pack.token_report({"tokens_total": 5000})
    app = CockpitApp(pack)
    events = app._pack.read_trace()
    assert "tokens: 5000" in status_line(events, tokens_total=app._tokens_from_report())
