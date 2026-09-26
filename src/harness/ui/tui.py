"""Foreman TUI cockpit (milestone 3, issues 3.13-3.16 re-scoped).

The spec's web dashboard cannot run in the evaluation environment; the
cockpit is a Textual app over the same evidence the pipeline writes. It
renders the live trace (activity log), the token meter, and the outcome -
`make run` launches it when a TTY is present and prints the headless
health summary otherwise.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, RichLog, Static

from harness.engine.evidence import EvidencePack


def format_event(event: dict[str, Any]) -> str:
    """Render one trace event to a log line (pure; testable without Textual)."""
    kind = event.get("event", "?")
    run_id = event.get("run_id", "-")
    if kind == "specialist.result":
        return (
            f"[{run_id}] {event.get('task')} -> "
            f"{'OK' if event.get('success') else 'FAIL'}: "
            f"{str(event.get('summary', ''))[:120]}"
        )
    if kind == "specialist.assigned":
        return f"[{run_id}] {event.get('task')} assigned to {event.get('agent')}"
    if kind == "run.end":
        return f"[{run_id}] run finished: {'SUCCESS' if event.get('success') else 'FAILED'}"
    return f"[{run_id}] {kind}"


def status_line(events: list[dict[str, Any]], tokens_total: int | None = None) -> str:
    """Render the status meter line (pure; testable without Textual).

    `tokens_total` comes from the pack's token-report.json when present —
    it is the authoritative spend; the per-event sum is the fallback.
    """
    if tokens_total is None:
        tokens_total = 0
        for event in events:
            usage = event.get("usage") or {}
            tokens_total += int(usage.get("total_tokens", 0))
    run_id = events[0].get("run_id", "-") if events else "(none)"
    return f"run: {run_id}  events: {len(events)}  tokens: {tokens_total}"


class CockpitApp(App[None]):  # pragma: no cover - Textual lifecycle, exercised manually
    """Live cockpit: activity log + token meter over an evidence pack.

    Rendering logic lives in the pure `format_event`/`status_line` functions
    above so the suite covers it without spinning up the Textual event loop
    (which is not headless-CI-safe across platforms).
    """

    TITLE = "Foreman Cockpit"
    CSS = """
    #status { height: 3; border: round $accent; padding: 0 1; }
    #activity { height: 1fr; border: round $primary; }
    """
    BINDINGS: ClassVar[list] = [("q", "quit", "Quit"), ("r", "refresh_trace", "Reload trace")]

    def __init__(self, pack: EvidencePack | None = None) -> None:
        super().__init__()
        self._pack = pack
        self.events: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("run: (none)  tokens: 0  mode: idle", id="status")
        yield RichLog(id="activity", markup=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_trace()

    def refresh_trace(self) -> None:
        log = self.query_one("#activity", RichLog)
        log.clear()
        self.events = self._pack.read_trace() if self._pack else []
        for event in self.events:
            self.query_one("#activity", RichLog).write(format_event(event))
        self.query_one("#status", Static).update(
            status_line(self.events, tokens_total=self._tokens_from_report())
        )

    def _tokens_from_report(self) -> int | None:
        """Authoritative spend from the pack's token-report.json, if present."""
        if self._pack is None:
            return None
        report = self._pack.path / "token-report.json"
        if not report.exists():
            return None
        try:
            return int(json.loads(report.read_text(encoding="utf-8"))["tokens_total"])
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            return None

    def add_event(self, event: dict[str, Any]) -> None:
        """Render one live trace event; also updates the status meter."""
        self.events.append(event)
        self.query_one("#activity", RichLog).write(format_event(event))
        self.query_one("#status", Static).update(
            status_line(self.events, tokens_total=self._tokens_from_report())
        )


def latest_evidence(results_root: Path) -> EvidencePack | None:
    """Most recently modified run directory, or None."""
    root = Path(results_root)
    if not root.exists():
        return None
    runs = sorted(
        (d for d in root.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime, reverse=True
    )
    if not runs:
        return None
    return EvidencePack(root, runs[0].name)
