"""Foreman TUI cockpit (milestone 3, issues 3.13-3.16 re-scoped & enhanced).

The cockpit is a Textual app over the same evidence the pipeline writes.
It renders the live trace (activity log), subtask plan tree, diff view,
verification test verdicts, and token meter — `make run` launches it when
a TTY is present and prints the headless health summary otherwise.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any, ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Footer, Header, Input, RichLog, Static, TabbedContent, TabPane

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
    """Live cockpit: interactive launcher + plan + activity + diff + tests + tokens.

    Rendering logic lives in the pure `format_event`/`status_line` functions
    above so the suite covers it without spinning up the Textual event loop.
    """

    TITLE = "Foreman Cockpit"
    CSS = """
    #status { height: 3; border: round $accent; padding: 0 1; }
    #launcher { height: 3; margin: 0 0 1 0; }
    #issue_input { width: 1fr; }
    #run_btn { width: 16; margin-left: 1; }
    #main_tabs { height: 1fr; border: round $primary; }
    #activity, #plan_box, #diff_box, #tests_box, #tokens_box { height: 1fr; }
    """
    BINDINGS: ClassVar[list] = [
        ("q", "quit", "Quit"),
        ("r", "refresh_trace", "Reload trace"),
        ("n", "focus_input", "New Task"),
    ]

    def __init__(self, pack: EvidencePack | None = None, repo_root: Path | None = None) -> None:
        super().__init__()
        self._pack = pack
        self._repo_root = repo_root or Path.cwd()
        self.events: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("run: (none)  tokens: 0  mode: idle", id="status")
        with Horizontal(id="launcher"):
            yield Input(
                placeholder="Enter goal (e.g. 'Build a CLI task manager', 'Create new app', 'Fix bug')...",
                id="issue_input",
            )
            yield Button("Run", id="run_btn", variant="primary")
        with TabbedContent(id="main_tabs"):
            with TabPane("Activity", id="tab_activity"):
                yield RichLog(id="activity", markup=False, wrap=True)
            with TabPane("Plan", id="tab_plan"):
                yield RichLog(id="plan_box", markup=False, wrap=True)
            with TabPane("Diff", id="tab_diff"):
                yield RichLog(id="diff_box", markup=False, wrap=True)
            with TabPane("Tests", id="tab_tests"):
                yield RichLog(id="tests_box", markup=False, wrap=True)
            with TabPane("Tokens", id="tab_tokens"):
                yield RichLog(id="tokens_box", markup=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_trace()

    def action_focus_input(self) -> None:
        """Focus the issue input box."""
        with contextlib.suppress(Exception):
            self.query_one("#issue_input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run_btn":
            self._trigger_run()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "issue_input":
            self._trigger_run()

    def _trigger_run(self) -> None:
        issue_input = self.query_one("#issue_input", Input)
        issue_text = issue_input.value.strip()
        if not issue_text:
            return
        issue_input.value = ""
        self.query_one("#status", Static).update(f"run: starting...  goal: {issue_text[:60]}")
        self.run_pipeline_worker(issue_text)

    @work(exclusive=True)
    async def run_pipeline_worker(self, issue_text: str) -> None:
        """Execute the harness pipeline asynchronously, streaming events to the UI."""
        import os

        from harness.config import ConfigLoader
        from harness.engine.pipeline import HarnessPipeline
        from harness.infrastructure.context_store import create_context_store
        from harness.infrastructure.model_providers import create_model_provider
        from harness.infrastructure.model_providers.fake import build_demo_provider

        try:
            config = ConfigLoader().load()
            key_env = config.models["default"].api_key_env
            demo_mode = os.environ.get("HARNESS_DEMO") == "1" or not os.environ.get(key_env)
            if demo_mode:
                provider = build_demo_provider(config.models["default"])
                if not os.environ.get(key_env):
                    self.query_one("#activity", RichLog).write(
                        f"[warn] '{key_env}' not set — running with demo/scripted provider (export {key_env} for live models)"
                    )
            else:
                provider = create_model_provider(config.models["default"])
            store = create_context_store(config.storage)
            pipeline = HarnessPipeline(
                repo_root=self._repo_root,
                config=config,
                provider=provider,
                store=store,
                event_sink=self.add_event,
            )
            outcome = await pipeline.run(issue_text, demo_mode=demo_mode)
            store.close()
            # Update diff and tests
            if outcome.evidence_path:
                patch_file = outcome.evidence_path / "patch.diff"
                if patch_file.exists():
                    self.query_one("#diff_box", RichLog).write(patch_file.read_text())
                test_file = outcome.evidence_path / "test-report.md"
                if test_file.exists():
                    self.query_one("#tests_box", RichLog).write(test_file.read_text())
                tok_file = outcome.evidence_path / "token-report.json"
                if tok_file.exists():
                    self.query_one("#tokens_box", RichLog).write(tok_file.read_text())
        except Exception as exc:
            self.query_one("#activity", RichLog).write(f"[error] pipeline failed: {exc}")

    def refresh_trace(self) -> None:
        log = self.query_one("#activity", RichLog)
        log.clear()
        self.events = self._pack.read_trace() if self._pack else []
        for event in self.events:
            self.query_one("#activity", RichLog).write(format_event(event))
        self.query_one("#status", Static).update(
            status_line(self.events, tokens_total=self._tokens_from_report())
        )
        self._populate_evidence_views()

    def _populate_evidence_views(self) -> None:
        """Populate Plan, Diff, Tests, and Tokens tabs from current evidence pack."""
        if not self._pack or not self._pack.path.exists():
            return
        try:
            diff_p = self._pack.path / "patch.diff"
            if diff_p.exists():
                diff_log = self.query_one("#diff_box", RichLog)
                diff_log.clear()
                diff_log.write(diff_p.read_text(encoding="utf-8"))

            test_p = self._pack.path / "test-report.md"
            if test_p.exists():
                test_log = self.query_one("#tests_box", RichLog)
                test_log.clear()
                test_log.write(test_p.read_text(encoding="utf-8"))

            tok_p = self._pack.path / "token-report.json"
            if tok_p.exists():
                tok_log = self.query_one("#tokens_box", RichLog)
                tok_log.clear()
                tok_log.write(tok_p.read_text(encoding="utf-8"))
        except Exception:
            pass

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
        """Render one live trace event; also updates the status meter and panes."""
        self.events.append(event)
        self.query_one("#activity", RichLog).write(format_event(event))
        self.query_one("#status", Static).update(
            status_line(self.events, tokens_total=self._tokens_from_report())
        )

        # Update Plan pane if task-related
        kind = event.get("event", "")
        if kind in ("specialist.assigned", "specialist.result"):
            task = event.get("task", "")
            agent = event.get("agent", "")
            summary = event.get("summary", "")
            success = "OK" if event.get("success") else "FAIL"
            self.query_one("#plan_box", RichLog).write(
                f"{kind}: task={task} agent={agent} status={success} {summary}"
            )
        elif kind == "verification.stage":
            stage = event.get("stage", "")
            passed = "PASS" if event.get("passed") else "FAIL"
            detail = event.get("detail", "")
            self.query_one("#tests_box", RichLog).write(f"[{passed}] Stage '{stage}': {detail}")


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
