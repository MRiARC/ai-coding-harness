"""Long-running process tools (M6): servers that stay up, status, clean stop.

`start_process` spawns a detached process (a dev server, a watcher) with its
output flowing to a log file under the state root; `check_process` reports
liveness + the log tail; `stop_process` terminates it. Names are the handles
— one process per name, duplicate starts refused while running.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from harness.tools.base import Tool, ToolResult, ToolTier

MAX_LOG_TAIL = 30


def _alive(pid: int) -> bool:
    """True when the pid is a living (non-zombie) process.

    os.kill(pid, 0) reports zombies as alive because the spawner hasn't
    reaped them; `ps` tells the truth (stat Z = dead).
    """
    import subprocess

    proc = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    stat = proc.stdout.strip()
    return bool(stat) and not stat.startswith("Z")


class _ProcessFiles:
    def __init__(self, state_root: Path) -> None:
        self.dir = Path(state_root) / "processes"
        self.dir.mkdir(parents=True, exist_ok=True)

    def log(self, name: str) -> Path:
        return self.dir / f"{name}.log"

    def pid(self, name: str) -> Path:
        return self.dir / f"{name}.pid"

    def read_pid(self, name: str) -> int | None:
        if not self.pid(name).is_file():
            return None
        try:
            return int(self.pid(name).read_text().strip())
        except ValueError:
            return None


class StartProcessTool(Tool):
    """start_process: spawn a detached long-running command (tier 3)."""

    name, tier = "start_process", ToolTier.ADVANCED
    description = (
        "Start a long-running command in the background (a dev server, a "
        "watcher). Args: name (short handle), command. Output goes to a log "
        "file; use check_process for status/output, stop_process to end it."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "command": {"type": "string"},
        },
        "required": ["name", "command"],
    }

    def __init__(self, scope: Path, state_root: Path) -> None:
        self._root = Path(scope)
        self._files = _ProcessFiles(state_root)

    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        name = arguments.get("name")
        if not isinstance(name, str) or not name.replace("-", "").replace("_", "").isalnum():
            errors.append("'name' must be alphanumeric with - or _")
        if not isinstance(arguments.get("command"), str) or not arguments["command"].strip():
            errors.append("'command' must be a non-empty string")
        return errors

    def check_permissions(self, context: dict[str, Any]) -> bool:
        return context.get("model_tier", 1) >= self.tier.value

    def _running(self, name: str) -> bool:
        pid = self._files.read_pid(name)
        return pid is not None and _alive(pid)

    def execute(self, name: str, command: str, **_: Any) -> ToolResult:
        if self._running(name):
            return ToolResult(
                success=False,
                error=f"'{name}' is already running (pid {self._files.read_pid(name)}); stop it first",
            )
        log = self._files.log(name)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w", encoding="utf-8") as handle:
            try:
                proc = subprocess.Popen(
                    ["/bin/zsh", "-c", command]
                    if Path("/bin/zsh").exists()
                    else ["/bin/bash", "-c", command],
                    cwd=str(self._root),
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            except OSError as exc:
                return ToolResult(success=False, error=f"cannot start process: {exc}")
        self._files.pid(name).write_text(str(proc.pid))
        return ToolResult(
            success=True,
            output=f"started '{name}' (pid {proc.pid}), log: {log}",
            data={"pid": proc.pid, "log": str(log)},
        )


class CheckProcessTool(Tool):
    """check_process: liveness + log tail for a started process (tier 2)."""

    name, tier = "check_process", ToolTier.DEVELOPMENT
    description = "Check a background process started with start_process. Args: name."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }

    def __init__(self, scope: Path, state_root: Path) -> None:
        self._files = _ProcessFiles(state_root)

    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        return [] if arguments.get("name") else ["'name' is required"]

    def check_permissions(self, context: dict[str, Any]) -> bool:
        return True

    def execute(self, name: str, **_: Any) -> ToolResult:
        pid = self._files.read_pid(name)
        if pid is None:
            return ToolResult(success=False, error=f"no process named '{name}'")
        running = _alive(pid)
        log = self._files.log(name)
        tail: list[str] = []
        if log.is_file():
            tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-MAX_LOG_TAIL:]
        status = "running" if running else "exited"
        return ToolResult(
            success=True,
            output=f"{name}: {status} (pid {pid})\n" + "\n".join(f"  {ln}" for ln in tail),
            data={"name": name, "pid": pid, "running": running},
        )


class StopProcessTool(Tool):
    """stop_process: terminate a background process (tier 2)."""

    name, tier = "stop_process", ToolTier.DEVELOPMENT
    description = "Stop a background process started with start_process. Args: name."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }

    def __init__(self, scope: Path, state_root: Path) -> None:
        self._files = _ProcessFiles(state_root)

    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        return [] if arguments.get("name") else ["'name' is required"]

    def check_permissions(self, context: dict[str, Any]) -> bool:
        return True

    def execute(self, name: str, **_: Any) -> ToolResult:
        pid = self._files.read_pid(name)
        if pid is None:
            return ToolResult(success=False, error=f"no process named '{name}'")
        if _alive(pid):
            try:
                # the spawn used start_new_session, so the pid is a process
                # group leader: kill the group, or children (sleep, servers)
                # survive the parent's death
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                for _attempt in range(10):
                    if not _alive(pid):
                        break
                    time.sleep(0.1)
                else:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            time.sleep(0.1)
        # the pid file stays: check_process reports "exited" instead of
        # pretending the process never existed
        return ToolResult(success=True, output=f"stopped '{name}' (pid {pid})")
