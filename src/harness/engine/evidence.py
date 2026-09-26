"""Evidence packs (the 'evidence over claims' deliverable).

One directory per run under `results/<run-id>/`: the patch, the full JSONL
decision trace, the verification report, the token report, and a human
readable summary. Judges - and our own debugging - can replay everything.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class EvidencePack:
    """Filesystem writer for one run's artifacts."""

    def __init__(self, results_root: Path, run_id: str) -> None:
        self.run_id = run_id
        self.path = Path(results_root) / run_id
        self.path.mkdir(parents=True, exist_ok=True)

    def _write(self, name: str, content: str) -> Path:
        target = self.path / name
        target.write_text(content, encoding="utf-8")
        return target

    def baseline_report(self, data: dict[str, Any]) -> Path:
        """Persist the pre-patch baseline snapshot (reproduction-first)."""
        return self._write("baseline.json", json.dumps(data, indent=2, sort_keys=True))

    def trace(self, event: dict[str, Any]) -> None:
        """Append one JSONL trace event (the audit spine of the run)."""
        with (self.path / "trace.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True, default=str) + "\n")

    def patch(self, diff: str) -> Path:
        return self._write("patch.diff", diff)

    def test_report(self, markdown: str) -> Path:
        return self._write("test-report.md", markdown)

    def token_report(self, metrics: dict[str, Any]) -> Path:
        return self._write(
            "token-report.json", json.dumps(metrics, indent=2, sort_keys=True, default=str)
        )

    def summary(self, markdown: str) -> Path:
        return self._write("summary.md", markdown)

    def read_trace(self) -> list[dict[str, Any]]:
        trace_path = self.path / "trace.jsonl"
        if not trace_path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in trace_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out


def find_evidence(results_root: Path, run_id: str | None = None) -> EvidencePack | None:
    """Locate one run's evidence pack: explicit id, else the most recent."""
    root = Path(results_root)
    if not root.exists():
        return None
    if run_id is None:
        runs = sorted(
            (d for d in root.iterdir() if d.is_dir()), key=lambda d: d.stat().st_mtime, reverse=True
        )
        if not runs:
            return None
        run_id = runs[0].name
    if not (root / run_id).is_dir():
        return None
    return EvidencePack(root, run_id)


def build_summary(
    run_id: str,
    issue_text: str,
    plan_markdown: str,
    stage_report: str,
    outcome_line: str,
    flags: list[str],
) -> str:
    """Assemble summary.md from the run's parts (honest, auditable)."""
    sections = [
        f"# Run {run_id}",
        "",
        f"**Outcome:** {outcome_line}",
        "",
        "## Issue",
        issue_text.strip()[:4000],
        "",
        "## Plan",
        plan_markdown,
        "",
        "## Verification",
        stage_report,
        "",
    ]
    if flags:
        sections += ["## Security flags", *[f"- {flag}" for flag in flags], ""]
    return "\n".join(sections)
