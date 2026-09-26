"""Extended CLI tests: valid-config path, subprocess entry points (issue 1.8)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from harness.cli import main

VALID_CONFIG = """\
models:
  default:
    provider: fake
    name: fake-model
    api_key_env: AI_API_KEY
agents:
  - agent_id: a-1
    role: verifier
    model: default
"""


def test_doctor_with_valid_config_and_key(isolated_env, monkeypatch, capsys) -> None:
    (isolated_env / "harness.yaml").write_text(VALID_CONFIG)
    monkeypatch.setenv("AI_API_KEY", "test-key")
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "configuration valid" in out
    assert "environment ready" in out


def test_doctor_valid_config_missing_key_warns_only(isolated_env, capsys) -> None:
    (isolated_env / "harness.yaml").write_text(VALID_CONFIG)
    assert main(["doctor"]) == 0
    assert "offline/test mode" in capsys.readouterr().out


def test_python_dash_m_harness_doctor(monkeypatch, isolated_env) -> None:
    """`python -m harness doctor` (the make run target) in-process for coverage."""
    import runpy

    monkeypatch.setattr(sys, "argv", ["harness", "doctor"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("harness", run_name="__main__")
    assert excinfo.value.code == 0


def test_direct_cli_script_execution(monkeypatch) -> None:
    """Executing cli.py as a script covers its __main__ guard."""
    import runpy

    cli_path = Path(__file__).resolve().parents[2] / "src" / "harness" / "cli.py"
    monkeypatch.setattr(sys, "argv", ["cli.py", "--version"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(cli_path), run_name="__main__")
    assert excinfo.value.code == 0
