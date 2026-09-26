"""Diff integrity classification (Milestone 4.10; improvements §1.3).

Making tests pass by editing tests is the classic agent failure mode. Before
verification, the diff is classified statically: modifications to test files
are violations unless the plan explicitly allows them, and debug-print
additions are flagged as diff-minimality warnings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch

TEST_FILE_PATTERNS = (
    "test_*.py",
    "*_test.py",
    "conftest.py",
    "test_*.js",
    "*.test.js",
    "*.spec.js",
    "*.spec.ts",
)

DEBUG_MARKERS = ("print(", "console.log(", "breakpoint()", "dbg!", "pdb.set_trace()")


def is_test_file(path: str) -> bool:
    """Whether a repo-relative path looks like a test file."""
    name = path.replace("\\", "/")
    segments = name.split("/")
    if any(segment in {"tests", "__tests__", "spec"} for segment in segments[:-1]):
        return True
    basename = segments[-1]
    return any(fnmatch(basename, pattern) for pattern in TEST_FILE_PATTERNS)


def changed_files(diff: str) -> list[str]:
    """Repo-relative files touched by a unified diff (`+++ b/` lines)."""
    files: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            name = line[6:].strip()
            if name and name != "/dev/null":
                files.append(name)
    return files


@dataclass
class IntegrityReport:
    """Static classification of one diff against the integrity policy."""

    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def classify_diff(diff: str, allow_test_edits: bool = False) -> IntegrityReport:
    """Violations block the run; warnings are advisory evidence only."""
    report = IntegrityReport()
    for path in changed_files(diff):
        if is_test_file(path) and not allow_test_edits:
            report.violations.append(f"test file modified without plan allowance: {path}")
    for line in diff.splitlines():
        if (
            line.startswith("+")
            and not line.startswith("+++")
            and any(marker in line for marker in DEBUG_MARKERS)
        ):
            report.warnings.append(f"debug output added: {line[1:].strip()[:120]}")
    return report
