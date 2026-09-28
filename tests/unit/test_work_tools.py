"""M6: work-mode tools — a real shell and long-running processes.

The eval toolbelt stays sandboxed; chat/work mode gets `run_shell` (any
command, scoped, timeout-capped, blocklist-guarded) and process control
(start/check/stop) so the agent can run servers and hand the user a URL.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.state import is_broad_scope, state_root
from harness.tools.processes import CheckProcessTool, StartProcessTool, StopProcessTool
from harness.tools.registry import build_default_tools, build_work_tools
from harness.tools.shell import RunShellTool


def test_eval_toolbelt_unchanged() -> None:
    """The graded eval path never receives work-mode tools (spec R2)."""
    tools = {t.name for t in build_default_tools(Path("."))}
    assert "run_shell" not in tools
    assert "start_process" not in tools


def test_work_toolbelt_adds_four() -> None:
    tools = {t.name: t for t in build_work_tools(Path("."), Path("/tmp/fs-state"))}
    assert {"run_shell", "start_process", "check_process", "stop_process"} <= set(tools)


# -- state placement ---------------------------------------------------------


def test_project_scope_keeps_state_inside(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = home / "code" / "myproject"
    project.mkdir(parents=True)
    assert state_root(project) == project / ".harness"
    assert not is_broad_scope(project)


def test_broad_scopes_go_to_foreman_home(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    for scope in (home, home / "Desktop", home / "Downloads"):
        scope.mkdir()
        root = state_root(scope)
        assert str(home / ".foreman") in str(root)
        assert is_broad_scope(scope)
    tmp_scope = Path("/tmp/whatever")
    assert is_broad_scope(tmp_scope)


# -- run_shell -----------------------------------------------------------------


def test_run_shell_runs_command(tmp_path: Path) -> None:
    tool = RunShellTool(tmp_path)
    result = tool.validate_input({"command": "echo hello"})
    assert result == []
    import asyncio

    outcome = asyncio.run(tool.execute_async(command="echo hello"))
    assert outcome.success and "hello" in outcome.output
    assert outcome.data["exit_code"] == 0


def test_run_shell_reports_failure(tmp_path: Path) -> None:
    import asyncio

    tool = RunShellTool(tmp_path)
    outcome = asyncio.run(tool.execute_async(command="exit 3"))
    assert not outcome.success and "exit 3" in (outcome.error or "")


def test_run_shell_cwd_is_scope(tmp_path: Path) -> None:
    import asyncio

    marker = tmp_path / "marker.txt"
    marker.write_text("here\n")
    tool = RunShellTool(tmp_path)
    outcome = asyncio.run(tool.execute_async(command="cat marker.txt"))
    assert outcome.success and "here" in outcome.output


def test_run_shell_validation_and_blocklist(tmp_path: Path) -> None:
    tool = RunShellTool(tmp_path)
    assert "'command' must be a non-empty string" in tool.validate_input({"command": "  "})
    assert "timeout_seconds" in tool.validate_input({"command": "ls", "timeout_seconds": 999})[0]
    blocked = tool.validate_input({"command": "sudo rm -rf /usr"})
    assert any("safety policy" in err for err in blocked)


def test_run_shell_timeout_kills(tmp_path: Path) -> None:
    import asyncio

    tool = RunShellTool(tmp_path)
    outcome = asyncio.run(tool.execute_async(command="sleep 5", timeout_seconds=1))
    assert not outcome.success and "timeout" in (outcome.error or "")


def test_run_shell_output_truncated(tmp_path: Path) -> None:
    import asyncio

    tool = RunShellTool(tmp_path)
    outcome = asyncio.run(
        tool.execute_async(command="python3 -c \"print('x' * 40000)\"", timeout_seconds=30)
    )
    assert "truncated at" in outcome.output


# -- processes ------------------------------------------------------------------


@pytest.fixture
def proc_tools(tmp_path: Path):
    scope = tmp_path / "ws"
    scope.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    return (
        StartProcessTool(scope, state),
        CheckProcessTool(scope, state),
        StopProcessTool(scope, state),
    )


def test_process_lifecycle(proc_tools) -> None:
    start, check, stop = proc_tools
    started = start.execute(name="demo", command="echo started && sleep 30")
    assert started.success
    pid = started.data["pid"]
    import time

    time.sleep(0.3)  # let the child flush its first log line

    checked = check.execute(name="demo")
    assert "running" in checked.output and "started" in checked.output

    stopped = stop.execute(name="demo")
    assert stopped.success
    import time

    time.sleep(0.5)  # SIGTERM to the process group lands
    assert not check.execute(name="demo").data["running"]


def test_start_refuses_duplicate_running(proc_tools) -> None:
    start, _check, stop = proc_tools
    start.execute(name="dup", command="sleep 30")
    dup = start.execute(name="dup", command="sleep 30")
    assert not dup.success and "already running" in (dup.error or "")
    stop.execute(name="dup")


def test_check_and_stop_unknown_process(proc_tools) -> None:
    _start, check, stop = proc_tools
    assert "no process named" in (check.execute(name="ghost").error or "")
    assert "no process named" in (stop.execute(name="ghost").error or "")


def test_process_validation(proc_tools, tmp_path: Path) -> None:
    start, check, stop = proc_tools
    assert start.validate_input({"name": "bad name!", "command": "x"})
    assert start.validate_input({"name": "ok", "command": ""})
    assert check.validate_input({}) and stop.validate_input({})
    # a valid state root but a missing scope dir: Popen cwd fails → clean error
    missing_scope = tmp_path / "missing-ws"
    start_missing = StartProcessTool(missing_scope, tmp_path / "state-ok")
    bad = start_missing.execute(name="x", command="echo hi")
    assert not bad.success and "cannot start process" in (bad.error or "")
