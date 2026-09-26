"""Input security layer (milestone 3, issue 3.7).

Three pure, deterministic gates used everywhere the harness touches the
outside world: prompt-injection detection for task text, path confinement
for every filesystem tool, and command whitelisting for execution tools.
"""

from __future__ import annotations

import re
from pathlib import Path

INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"ignore (all |any )?(previous|prior|above) (instructions|prompts|rules)",
        r"disregard (all |any )?(previous|prior|above)",
        r"you are now (a|an|the)",
        r"print (your|the) (system )?(prompt|instructions)",
        r"reveal (your|the) (system )?(prompt|instructions)",
        r"ignore .{0,40}and .{0,40}(instead|now)",
        r"new instructions?:",
        r"system:\s*you",
    )
)

SHELL_METACHARACTERS = re.compile(r"[;|&$`<>\\\n]")


def detect_prompt_injection(text: str) -> list[str]:
    """Return the matched injection patterns (empty list = clean)."""
    return [pattern.pattern for pattern in INJECTION_PATTERNS if pattern.search(text)]


def sanitize_path(root: Path, relative: str) -> Path:
    """Resolve `relative` inside `root`; refuse anything escaping it.

    Blocks absolute paths, `..` traversal, and symlink escapes - the
    directory-traversal gate required by issue 3.7.
    """
    if not relative:
        msg = "empty path"
        raise ValueError(msg)
    candidate = Path(relative)
    if candidate.is_absolute():
        msg = f"absolute paths are not allowed: {relative}"
        raise ValueError(msg)
    resolved = (root / candidate).resolve()
    root_resolved = root.resolve()
    if not resolved.is_relative_to(root_resolved):
        msg = f"path escapes the repository root: {relative}"
        raise ValueError(msg)
    return resolved


def validate_command(allowed_commands: tuple[str, ...] | list[str], argv: list[str]) -> list[str]:
    """Whitelist-check an argv vector; refuse metacharacters anywhere in it."""
    errors: list[str] = []
    if not argv:
        return ["empty command"]
    if argv[0] not in allowed_commands:
        errors.append(
            f"command '{argv[0]}' is not allowlisted (allowed: {', '.join(allowed_commands)})"
        )
    for arg in argv:
        if SHELL_METACHARACTERS.search(arg):
            errors.append(f"shell metacharacter in argument: {arg[:60]!r}")
    return errors
