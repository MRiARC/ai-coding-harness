"""Work-mode tools: a real shell and long-running processes.

These exist for chat/work mode only — the graded eval toolbelt never
receives them (spec v1.1 §18 R2: the evaluation path stays sandboxed).
`run_shell` trades the eval allowlist for accountability: everything runs
inside the declared scope, is timeout-capped, output-capped, and logged to
the trace. Process tools add what a terminal gives you: servers that stay
up, status checks, and a clean stop.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from harness.tools.base import AsyncExecutableTool, ToolResult, ToolTier

MAX_SHELL_OUTPUT = 20_000
DEFAULT_SHELL_TIMEOUT = 60.0
MAX_SHELL_TIMEOUT = 300.0

BLOCKLIST = (
    r"rm\s+(-[a-z]+\s+)*-?[a-z]*r[a-z]*f",
    r"\bsudo\b",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bdd\s+if=",
    r":\(\)\s*\{.*\};:",
    r"\bfork\b.*\bbomb\b",
)

PROCESS_LOG_LINES = 30


def _truncate(text: str) -> str:
    if len(text) <= MAX_SHELL_OUTPUT:
        return text
    return text[:MAX_SHELL_OUTPUT] + f"\n... [truncated at {MAX_SHELL_OUTPUT} bytes]"


def _blocked(command: str) -> str | None:
    import re

    for pattern in BLOCKLIST:
        if re.search(pattern, command, re.IGNORECASE):
            return pattern
    return None


def _shell_argv() -> list[str]:
    for shell in ("/bin/zsh", "/bin/bash"):
        if Path(shell).exists():
            return [shell, "-c"]
    return ["/bin/sh", "-c"]


class RunShellTool(AsyncExecutableTool):
    """run_shell: execute a shell command inside the scope (tier 3, work mode).

    The free-spirited counterpart to the eval allowlist: any command runs,
    but everything is scoped (cwd = workspace root), timeout-capped,
    output-capped, blocklist-guarded, and fully logged to the trace.
    """

    name, tier = "run_shell", ToolTier.ADVANCED
    description = (
        "Run a shell command in the workspace (zsh). Args: command (string), "
        "timeout_seconds (optional, 60 default, 300 max). Returns stdout+stderr "
        "and the exit code."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout_seconds": {"type": "integer"},
        },
        "required": ["command"],
    }

    def __init__(self, scope: Path) -> None:
        self._root = Path(scope)

    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        if not isinstance(arguments.get("command"), str) or not arguments["command"].strip():
            return ["'command' must be a non-empty string"]
        # safety policy first: a blocked command is denied even if other
        # arguments are also wrong
        if blocked := _blocked(arguments["command"]):
            return [f"command blocked by safety policy (matched: {blocked})"]
        timeout = arguments.get("timeout_seconds", DEFAULT_SHELL_TIMEOUT)
        if not isinstance(timeout, (int, float)) or not 1 <= timeout <= MAX_SHELL_TIMEOUT:
            return [f"'timeout_seconds' must be a number in [1, {MAX_SHELL_TIMEOUT}]"]
        return []

    def check_permissions(self, context: dict[str, Any]) -> bool:
        return context.get("model_tier", 1) >= self.tier.value

    def execute(self, **_: Any) -> ToolResult:  # pragma: no cover - async path used
        return ToolResult(success=False, error="use execute_async (run_shell is async)")

    async def execute_async(self, command: str, timeout_seconds: int = 60, **_: Any) -> ToolResult:
        argv = [*_shell_argv(), command]
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(self._root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except OSError as exc:
            return ToolResult(success=False, error=f"cannot spawn shell: {exc}")
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout_seconds)
        except TimeoutError:
            proc.kill()
            return ToolResult(
                success=False,
                error=f"command exceeded {timeout_seconds}s timeout (killed)",
                data={"exit_code": None},
            )
        output = _truncate(
            f"{stdout.decode(errors='replace')}\n{stderr.decode(errors='replace')}".strip()
        )
        passed = proc.returncode == 0
        return ToolResult(
            success=passed,
            output=output,
            error=None if passed else f"exit {proc.returncode}",
            data={"exit_code": proc.returncode},
        )
