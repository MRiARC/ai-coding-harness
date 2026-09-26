"""Execution tools: test runner, sandbox, security scan (issues 3.2-3.3)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from harness.tools.execution import (
    CodeExecutionTool,
    RunTestsTool,
    SecurityScanTool,
    detect_test_runner,
)


@pytest.fixture
def py_repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n")
    (tmp_path / "test_bad.py").write_text("def test_bad():\n    assert 1 + 1 == 3\n")
    return tmp_path


def test_detect_test_runner(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("")
    name, command = detect_test_runner(tmp_path)
    assert name == "pytest" and command[1:3] == ["-m", "pytest"]
    (tmp_path / "pyproject.toml").unlink()
    (tmp_path / "package.json").write_text("{}")
    assert detect_test_runner(tmp_path)[0] == "npm"
    (tmp_path / "package.json").unlink()
    (tmp_path / "Makefile").write_text("")
    assert detect_test_runner(tmp_path)[0] == "make"
    (tmp_path / "Makefile").unlink()
    assert detect_test_runner(tmp_path) == ("none", [])


def test_run_tests_pass_and_fail(py_repo) -> None:
    tool = RunTestsTool(py_repo)
    ok = tool.execute(path="test_ok.py")
    assert ok.success and ok.data["framework"] == "pytest"
    bad = tool.execute(path="test_bad.py")
    assert not bad.success and "tests failed" in bad.error


def test_run_tests_no_runner(tmp_path: Path) -> None:
    assert not RunTestsTool(tmp_path).execute().success


def test_run_tests_timeout(py_repo, monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1)

    monkeypatch.setattr(subprocess, "run", explode)
    result = RunTestsTool(py_repo).execute()
    assert not result.success and "timeout" in result.error


def test_code_execution_allowlisted(py_repo) -> None:
    tool = CodeExecutionTool(py_repo)
    tool.execute(command=[sys.executable, "-c", "print('sandbox-ok')"])
    # argv[0] must be allowlisted; sys.executable is not -> validate first
    assert tool.validate_input({"command": [sys.executable, "-c", "x"]}) != []
    assert tool.validate_input({"command": ["python", "-c", "print(1)"]}) == []
    assert tool.validate_input({"command": []}) != []
    assert tool.validate_input({"command": "rm -rf"}) != []
    assert tool.validate_input({"command": ["python", "-c", "x; rm"]}) != []  # metachar


def test_code_execution_runs_and_confines(py_repo) -> None:
    tool = CodeExecutionTool(py_repo)
    result = tool.execute(command=["python", "-c", "print('sandbox-ok')"])
    assert result.success and "sandbox-ok" in result.output
    assert result.data["confined_to"] == str(py_repo)
    bad = tool.execute(command=["python", "-c", "raise SystemExit(3)"])
    assert not bad.success and bad.error == "exit 3"
    assert not tool.check_permissions({"model_tier": 2})
    assert tool.check_permissions({"model_tier": 3})


def test_code_execution_timeout(py_repo, monkeypatch) -> None:
    def explode(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="python", timeout=30)

    monkeypatch.setattr(subprocess, "run", explode)
    result = CodeExecutionTool(py_repo).execute(command=["python", "-c", "1"])
    assert not result.success and "sandbox timeout" in result.error


def test_code_execution_output_truncation(py_repo, monkeypatch) -> None:
    import harness.tools.execution as execution

    monkeypatch.setattr(execution, "MAX_OUTPUT_BYTES", 10)
    result = CodeExecutionTool(py_repo).execute(command=["python", "-c", "print('A' * 500)"])
    assert "truncated at 10 bytes" in result.output


def test_security_scan_clean_and_findings(tmp_path: Path) -> None:
    (tmp_path / "clean.py").write_text("x = 1\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("password = leaked_in_git_dir\n")

    clean = SecurityScanTool(tmp_path).execute()  # .git/ skipped, no findings
    assert clean.success and clean.data["findings"] == 0

    (tmp_path / "leak.py").write_text(
        'AWS_ID = "AKIAIOSFODNN7EXAMPLE"\n'
        "password = hunter2secret\n"
        "token = 'ghp_abcdefghijklmnopqrstuvwxyz0123456789'\n"
    )
    findings = SecurityScanTool(tmp_path).execute()
    assert not findings.success and len(findings.data["findings"]) >= 2
    assert not SecurityScanTool(tmp_path).execute(path="../outside").success
    assert not SecurityScanTool(tmp_path).execute(path="ghost.py").success


def test_detect_test_runner_bare_test_files(tmp_path: Path) -> None:
    (tmp_path / "test_app.py").write_text("def test_x():\n    pass\n")
    (tmp_path / "app.py").write_text("x = 1\n")
    assert detect_test_runner(tmp_path)[0] == "pytest"
