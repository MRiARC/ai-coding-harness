"""A/B comparison driver: current tree vs a git ref (or a saved baseline).

`harness bench` (or `make bench-tokens`) runs the offline fixture through the
real pipeline in a subprocess for each side, then prints the per-agent
prompt/completion delta. `--ref <git-ref>` measures a baseline worktree
(detached checkout, cleaned up afterwards); `--save-baseline` records the
current spend for later comparisons.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from harness.bench.runner import FIXTURE_ISSUE

BASELINE_RELPATH = Path("docs/evidence/bench-baseline.json")
COMPARABLE_TOKEN_KEYS = ("tokens_total", "tasks_completed")


def _runner_path() -> Path:
    import harness.bench.runner as runner_module

    return Path(runner_module.__file__)


def run_measurement(src_dir: Path | None, issue: str = FIXTURE_ISSUE) -> dict[str, Any]:
    """Run one measurement in a subprocess against `src_dir` (None = installed)."""
    env = dict(os.environ)
    if src_dir is not None:
        env["PYTHONPATH"] = str(src_dir)
    proc = subprocess.run(
        [sys.executable, str(_runner_path()), "--issue", issue],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
        check=False,
    )
    if proc.returncode != 0:
        msg = f"bench runner failed (exit {proc.returncode}):\n{proc.stderr[-2000:]}"
        raise RuntimeError(msg)
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        msg = "bench runner produced no output"
        raise RuntimeError(msg)
    result: dict[str, Any] = json.loads(lines[-1])
    return result


def compare(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Per-agent + total token delta (positive = candidate spends MORE)."""
    base_agents: dict[str, Any] = baseline.get("token_report", {}).get("per_agent_tokens", {})
    cand_agents: dict[str, Any] = candidate.get("token_report", {}).get("per_agent_tokens", {})

    def _delta(base: dict[str, int], cand: dict[str, int]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            b, c = int(base.get(key, 0)), int(cand.get(key, 0))
            out[key] = {"baseline": b, "candidate": c, "delta": c - b}
            out[key]["pct"] = round(100 * (c - b) / b, 1) if b else None
        return out

    agents = {
        name: _delta(base_agents.get(name, {}), cand_agents.get(name, {}))
        for name in sorted(set(base_agents) | set(cand_agents))
    }
    totals: dict[str, Any] = {}
    for key in COMPARABLE_TOKEN_KEYS:
        b = int(baseline.get("token_report", {}).get(key, 0))
        c = int(candidate.get("token_report", {}).get(key, 0))
        totals[key] = {"baseline": b, "candidate": c, "delta": c - b}
        totals[key]["pct"] = round(100 * (c - b) / b, 1) if b else None
    return {"per_agent": agents, "totals": totals}


def render_table(delta: dict[str, Any]) -> str:
    """Human-readable comparison table (tokens; negative delta = saving)."""

    def row(label: str, entry: dict[str, Any]) -> str:
        b, c, d = entry["baseline"], entry["candidate"], entry["delta"]
        pct = f"{entry['pct']:+.1f}%" if entry["pct"] is not None else "n/a"
        return f"{label:<24} {b:>10,} {c:>10,} {d:>+10,} {pct:>8}"

    lines = [
        f"{'agent/metric':<24} {'baseline':>10} {'candidate':>10} {'delta':>10} {'pct':>8}",
        "-" * 66,
    ]
    for name, agent in delta["per_agent"].items():
        lines.append(row(name, agent["total_tokens"]))
    lines.append("-" * 66)
    for key in ("tokens_total", "tasks_completed"):
        lines.append(row(f"TOTAL {key}", delta["totals"][key]))
    return "\n".join(lines)


def _baseline_from_ref(repo_root: Path, ref: str) -> dict[str, Any]:
    """Measure a git ref in a detached temporary worktree (cleaned up after)."""
    worktree = Path(tempfile.mkdtemp(prefix="harness-bench-ref-"))
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "add", "--detach", str(worktree), ref],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        worktree.rmdir()
        msg = f"cannot create worktree for ref '{ref}': {proc.stderr.strip()}"
        raise RuntimeError(msg)
    try:
        return run_measurement(worktree / "src")
    finally:
        subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(worktree)],
            capture_output=True,
            text=True,
            check=False,
        )
        subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "prune"],
            capture_output=True,
            text=True,
            check=False,
        )


def main(argv: list[str] | None = None) -> int:
    """`harness bench`: measure, compare, print; optional baseline save."""
    parser = argparse.ArgumentParser(
        prog="harness bench", description="A/B token benchmark on the offline fixture"
    )
    parser.add_argument("--issue", default=FIXTURE_ISSUE)
    parser.add_argument("--ref", default=None, help="git ref to measure as the baseline side")
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="record the current measurement as the baseline for future runs",
    )
    parser.add_argument(
        "--baseline-path",
        default=None,
        help=f"path to the baseline JSON (default: {BASELINE_RELPATH})",
    )
    parser.add_argument("--json-out", default=None, help="write the full delta JSON here")
    args = parser.parse_args(argv)

    # Resolve the baseline side first: a bad --ref should fail before we
    # spend the candidate run.
    baseline: dict[str, Any] | None = None
    if args.ref:
        repo_root = Path.cwd()
        baseline = _baseline_from_ref(repo_root, args.ref)
    else:
        baseline_path = Path(args.baseline_path) if args.baseline_path else BASELINE_RELPATH
        if baseline_path.exists():
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    candidate = run_measurement(None, args.issue)
    if not candidate.get("success"):
        print(f"[error] candidate run did not reach VERIFIED: {candidate.get('outcome_line')}")
        return 1

    if baseline is None:
        print("[info] no baseline (--ref or --save-baseline); showing current spend only")
        report = candidate.get("token_report", {})
        print(f"tokens_total: {report.get('tokens_total', 0):,}")
        for name, usage in report.get("per_agent_tokens", {}).items():
            print(f"  {name:<22} {usage.get('total_tokens', 0):>10,}")
    else:
        delta = compare(baseline, candidate)
        print(render_table(delta))
        if args.json_out:
            Path(args.json_out).write_text(
                json.dumps(
                    {"baseline": baseline, "candidate": candidate, "delta": delta}, indent=2
                ),
                encoding="utf-8",
            )
            print(f"[ok] delta JSON written: {args.json_out}")

    if args.save_baseline:
        baseline_path = Path(args.baseline_path) if args.baseline_path else BASELINE_RELPATH
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(candidate, indent=2), encoding="utf-8")
        print(f"[ok] baseline saved: {baseline_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
