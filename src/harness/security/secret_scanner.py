"""Secret detection (milestone 3, issue 3.9).

Scans text, diffs, and directory trees for credential patterns before they
can reach a commit, and enforces the file-level permission policy
(.env read-only, secrets/ blocked, src/auth/ + migrations/ flagged).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "__pycache__", ".harness", "node_modules", "results"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    snippet: str


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (kind, re.compile(pattern))
    for kind, pattern in (
        ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
        ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
        (
            "api-key-assignment",
            re.compile(
                r"(?i)\b(api[_-]?key|secret|token|auth[_-]?token)\b['\"]?\s*[:=]\s*['\"]?"
                r"[A-Za-z0-9_\-]{16,}"
            ),
        ),
        (
            "password-assignment",
            re.compile(r"(?i)\b(password|passwd|pwd)\b['\"]?\s*[:=]\s*['\"]?[^\s'\"]{6,}"),
        ),
        (
            "connection-string",
            re.compile(r"(?i)\b(postgres(ql)?|mysql|mongodb(\+srv)?|redis)://[^\s:@/]+:[^\s@/]+@"),
        ),
        ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    )
)

BENIGN_VALUE = re.compile(
    r"^(x+$|\.+$|\*+|<[^>]+>|\$\{[A-Za-z_][A-Za-z0-9_]*\}|none|null|"
    r"test|dummy|example|changeme|placeholder|your[-_].*)$",
    re.IGNORECASE,
)


@dataclass
class PathPolicy:
    """File-level permission policy from issue 3.9."""

    blocked: bool = False
    read_only: bool = False
    requires_review: str | None = None


def check_path_policy(relative: str) -> PathPolicy:
    """Classify a repo-relative path per the issue-3.9 policy table."""
    normalized = relative.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    lowered = normalized.lower()
    parts = lowered.split("/")
    first = parts[0] if parts else ""
    if first in {"secrets", ".env"} or lowered in {".env", ".env.local"}:
        return PathPolicy(blocked=first == "secrets", read_only=True)
    if (len(parts) >= 2 and parts[0] == "src" and parts[1] == "auth") or first == "auth":
        return PathPolicy(requires_review="security review")
    if first == "migrations":
        return PathPolicy(requires_review="specialist approval")
    return PathPolicy()


def scan_text(text: str, path: str = "<text>") -> list[Finding]:
    """Return secret findings in one text blob (benign placeholders ignored)."""
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        for kind, pattern in SECRET_PATTERNS:
            match = pattern.search(stripped)
            if not match:
                continue
            value = match.group(0).split("=", 1)[-1].split(":", 1)[-1].strip("'\" ")
            if BENIGN_VALUE.match(value):
                continue
            findings.append(Finding(path=path, line=line_number, kind=kind, snippet=stripped[:120]))
            break  # one finding per line is enough signal
    return findings


def scan_path(root: Path, limit_files: int = 2000) -> list[Finding]:
    """Scan every readable file under `root` (bounded)."""
    findings: list[Finding] = []
    scanned = 0
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue
        try:
            if file_path.stat().st_size > 300_000:
                continue
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        scanned += 1
        if scanned > limit_files:
            break
        findings.extend(
            scan_text(
                text, str(file_path.relative_to(root)) if file_path != root else file_path.name
            )
        )
    return findings


def scan_diff(diff: str) -> list[Finding]:
    """Scan only added lines of a unified diff (pre-commit gate)."""
    added: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
    return scan_text("\n".join(added), "<diff>")


def block_reason(findings: list[Finding]) -> str | None:
    """Human-facing block message for a scan with findings (None = clean)."""
    if not findings:
        return None
    first = findings[0]
    return (
        f"secret detected: {first.kind} at {first.path}:{first.line} "
        f"- remove it and load the value from the environment instead"
    )
