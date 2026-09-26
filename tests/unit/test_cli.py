"""CLI tests: doctor exit codes (issue 1.8's "example tests" for the shell surface)."""

from __future__ import annotations

from harness.cli import main


def test_doctor_ok_without_key(isolated_env, capsys) -> None:
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "environment ready" in out
    assert "AI_API_KEY" in out  # warn-only, offline mode announced


def test_doctor_validates_config(isolated_env) -> None:
    (isolated_env / "harness.yaml").write_text(
        "agents:\n  - agent_id: a\n    role: verifier\n    model: nope\n"
    )
    assert main(["doctor"]) == 1


def test_version_flag(capsys) -> None:
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    assert "harness" in capsys.readouterr().out
