"""Verification pipeline (milestone 3, issues 3.4-3.6).

Five stages per DESIGN_SPEC §9, adapted to the unattended evaluation
environment: Stage 2's "CI/CD" is the local full test suite (no CI runners
exist at eval time; our own repo's CI covers the published-harness case).
Stages 1/2/5 are deterministic; Stage 3 is the AST smell pass (non-blocking
advisories); Stage 4 is the Architect's LLM review verdict.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.agents.architect import ArchitectAgent, Plan, ReviewVerdict
from harness.security.secret_scanner import block_reason, scan_diff
from harness.tools.editing import SyntaxCheckTool
from harness.tools.execution import RunTestsTool
from harness.verification.code_review import review_paths


@dataclass
class StageResult:
    name: str
    passed: bool
    detail: str = ""
    duration_seconds: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)
    blocking: bool = True


class VerificationPipeline:
    """Runs the quality gates over one change set and reports a verdict."""

    def __init__(self, repo_root: Path) -> None:
        self._root = repo_root
        self.results: list[StageResult] = []
        self.cancelled = False

    def changed_files(self, diff: str) -> list[str]:
        """Repo-relative files touched by a unified diff."""
        files: list[str] = []
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                files.append(line[6:])
        return files

    async def run(
        self, diff: str, plan: Plan | None, architect: ArchitectAgent | None = None
    ) -> list[StageResult]:
        """Execute stages 1-5 in order; stops at the first blocking failure."""
        self.results = []
        stages: tuple[Callable[..., Awaitable[StageResult]], ...] = (
            self._stage_self_check,
            self._stage_local_tests,
            self._stage_code_review,
            self._stage_security,
            self._stage_final_review,
        )
        for stage in stages:
            if self.cancelled:
                self.results.append(
                    StageResult(name="cancelled", passed=False, detail="pipeline cancelled")
                )
                break
            result = await _timed(stage, diff, plan, architect)
            self.results.append(result)
            if not result.passed and result.blocking:
                break
        return self.results

    # -- stages ---------------------------------------------------------------
    async def _stage_self_check(
        self, diff: str, plan: Plan | None, architect: ArchitectAgent | None
    ) -> StageResult:
        files = self.changed_files(diff)
        if not files:
            return StageResult("1-self-check", True, "no changed files to check")
        tool = SyntaxCheckTool(self._root)
        result = tool.execute(paths=files)
        return StageResult(
            "1-self-check", result.success, result.error or result.output, evidence={"files": files}
        )

    async def _stage_local_tests(
        self, diff: str, plan: Plan | None, architect: ArchitectAgent | None
    ) -> StageResult:
        tool = RunTestsTool(self._root)
        result = tool.execute()
        return StageResult(
            "2-local-tests",
            result.success,
            result.error or "test suite green",
            evidence={"output": result.output[-4000:]},
        )

    async def _stage_code_review(
        self, diff: str, plan: Plan | None, architect: ArchitectAgent | None
    ) -> StageResult:
        files = [self._root / rel for rel in self.changed_files(diff)]
        findings = review_paths(files, self._root)
        serialized = [
            {"path": f.path, "line": f.line, "kind": f.kind, "detail": f.detail} for f in findings
        ]
        return StageResult(
            "3-code-review",
            True,  # non-blocking advisories
            f"{len(findings)} advisory findings",
            blocking=False,
            evidence={"findings": serialized},
        )

    async def _stage_security(
        self, diff: str, plan: Plan | None, architect: ArchitectAgent | None
    ) -> StageResult:
        findings = scan_diff(diff)
        reason = block_reason(findings)
        return StageResult(
            "4-security",
            reason is None,
            reason or "no secrets in added lines",
            evidence={"finding_count": len(findings)},
        )

    async def _stage_final_review(
        self, diff: str, plan: Plan | None, architect: ArchitectAgent | None
    ) -> StageResult:
        if architect is None or plan is None:
            return StageResult(
                "5-final-review", True, "skipped (no architect/plan supplied)", blocking=False
            )
        verdict: ReviewVerdict = await architect.review(diff, plan)
        return StageResult(
            "5-final-review",
            verdict.approved,
            verdict.summary or ("approved" if verdict.approved else "; ".join(verdict.issues)),
            evidence={"issues": verdict.issues},
        )


async def _timed(
    stage: Callable[..., Awaitable[StageResult]],
    diff: str,
    plan: Plan | None,
    architect: ArchitectAgent | None,
) -> StageResult:
    started = time.monotonic()
    result = await stage(diff, plan, architect)
    result.duration_seconds = round(time.monotonic() - started, 3)
    return result


def stage_report(results: list[StageResult]) -> str:
    """Markdown summary of a pipeline run (evidence-pack input)."""
    lines = ["| Stage | Result | Detail | Duration |", "|---|---|---|---|"]
    for result in results:
        lines.append(
            f"| {result.name} | {'PASS' if result.passed else 'FAIL'} "
            f"| {result.detail[:160]} | {result.duration_seconds}s |"
        )
    overall = all(r.passed for r in results if r.blocking)
    lines.append("")
    lines.append(f"**Overall: {'VERIFIED' if overall else 'NOT VERIFIED'}**")
    return "\n".join(lines)
