"""Replay command, model probe, and phase metrics (Milestone 3 polish)."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.engine.evidence import EvidencePack, find_evidence
from harness.infrastructure.model_providers import FakeProvider, ModelResponse
from harness.monitoring.health import probe_model_health, run_health_checks


@pytest.fixture
def packed(tmp_path: Path) -> EvidencePack:
    pack = EvidencePack(tmp_path / "results", "run-replay")
    pack.trace({"event": "run.start", "run_id": "run-replay"})
    pack.trace(
        {
            "event": "specialist.result",
            "run_id": "run-replay",
            "task": "st-1",
            "success": True,
            "summary": "it works",
        }
    )
    pack.trace({"event": "run.end", "run_id": "run-replay", "success": True})
    return pack


def test_find_evidence(tmp_path: Path, packed: EvidencePack) -> None:
    assert find_evidence(tmp_path / "results", "run-replay") is not None
    assert find_evidence(tmp_path / "results", "ghost") is None
    assert find_evidence(tmp_path / "results", None).run_id == "run-replay"
    assert find_evidence(tmp_path / "results-missing") is None
    (tmp_path / "results" / "empty-dir").mkdir()
    assert find_evidence(tmp_path / "results", "empty-dir") is not None


def test_replay_headless(monkeypatch, tmp_path: Path, packed: EvidencePack, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    class FakeStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return ""

    monkeypatch.setattr("sys.stdin", FakeStdin())
    from harness.cli import replay_command

    assert replay_command(None) == 0
    out = capsys.readouterr().out
    assert "[run-replay] run.start" in out
    assert "[run-replay] st-1 -> OK: it works" in out
    assert "[ok] replayed run-replay (3 events)" in out


def test_replay_explicit_run_id(monkeypatch, tmp_path: Path, packed: EvidencePack, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    class FakeStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return ""

    monkeypatch.setattr("sys.stdin", FakeStdin())
    from harness.cli import replay_command

    assert replay_command("run-replay") == 0
    assert "run-replay" in capsys.readouterr().out


class FakeIsatty:
    def isatty(self) -> bool:
        return True


def test_replay_without_any_pack(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    class FakeStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return ""

    monkeypatch.setattr("sys.stdin", FakeStdin())
    from harness.cli import replay_command

    assert replay_command(None) == 1
    assert "no evidence pack" in capsys.readouterr().out


def test_doctor_probe_model_offline(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "harness.yaml").write_text(
        "models:\n  default:\n    provider: fake\n    name: fake-model\n"
    )
    from harness.cli import main

    assert main(["doctor", "--probe-model"]) == 0  # probe fails, warn-only
    assert "model probe" in capsys.readouterr().out


def test_probe_model_success_and_failure(fake_model_config) -> None:
    scripted = FakeProvider(
        fake_model_config,
        responses=[
            ModelResponse(content="pong"),
        ],
    )
    ok, detail = probe_model_health(fake_model_config, provider=scripted)
    assert ok and "replied" in detail
    failing = FakeProvider(fake_model_config, responses=[])
    ok, detail = probe_model_health(fake_model_config, provider=failing)
    assert not ok and "exhausted" in detail


def test_health_model_probe_flag(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "harness.yaml").write_text(
        "models:\n  default:\n    provider: fake\n    name: fake-model\n"
    )
    report = run_health_checks(tmp_path, model_probe=True)
    names = {c["name"] for c in report.checks}
    assert "model-api" in names  # fake provider: probe fails, non-required
    assert report.ready  # ...but readiness is unaffected


def test_health_probe_skipped_when_config_broken(tmp_path: Path) -> None:
    (tmp_path / "harness.yaml").write_text(
        "agents:\n  - agent_id: a\n    role: verifier\n    model: nope\n"
    )
    report = run_health_checks(tmp_path, config_path=tmp_path / "harness.yaml", model_probe=True)
    probe = next(c for c in report.checks if c["name"] == "model-api")
    assert "skipped" in probe["detail"]


def test_main_replay_dispatch(monkeypatch, tmp_path: Path, packed: EvidencePack, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    class FakeStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return ""

    monkeypatch.setattr("sys.stdin", FakeStdin())
    from harness.cli import main

    assert main(["replay", "run-replay"]) == 0
    assert "replayed run-replay" in capsys.readouterr().out


def test_main_replay_missing_pack(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    class FakeStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return ""

    monkeypatch.setattr("sys.stdin", FakeStdin())
    from harness.cli import main

    assert main(["replay"]) == 1
    assert "no evidence pack" in capsys.readouterr().out


def test_main_run_dispatch_headless(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    class FakeStdin:
        def isatty(self) -> bool:
            return False

        def read(self) -> str:
            return ""

    monkeypatch.setattr("sys.stdin", FakeStdin())
    from harness.cli import main

    assert main(["run"]) == 0
    assert "READY" in capsys.readouterr().out
