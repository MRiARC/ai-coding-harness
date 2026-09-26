"""Orchestrator service + Redis publisher tests (platform P1/P3, #70/#72)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from harness.config import HarnessConfig
from harness.service.app import create_app
from harness.service.events import RedisEventPublisher


class FakeRedis:
    """Minimal redis-like client recording publishes."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    def publish(self, channel: str, message: str) -> int:
        self.published.append((channel, message))
        return 1


@pytest.fixture
def demo_repo(tmp_path: Path) -> Path:
    (tmp_path / "target").mkdir()
    (tmp_path / "target" / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    (tmp_path / "target" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    (tmp_path / "target" / "app.py").write_text("def greet():\n    return 'hello'\n")
    (tmp_path / "harness.yaml").write_text(
        "models:\n  default:\n    provider: fake\n    name: fake-model\n"
        "agents:\n"
        "  - agent_id: arch-1\n    role: architect\n    model: default\n"
        "  - agent_id: mgr-1\n    role: manager\n    model: default\n"
        "  - agent_id: ver-1\n    role: verifier\n    model: default\n"
        "storage:\n  backend: memory\n"
    )
    return tmp_path


PROFILE = (
    '{"languages": ["Python"], "frameworks": [], "test_framework": "pytest", '
    '"build_system": "pyproject.toml", "conventions": [], "notes": ""}'
)
PLAN = (
    '{"issue_summary": "s", "complexity": 2, "subtasks": [{"id": "st-1", '
    '"title": "t", "description": "d", "specialty": "verification", '
    '"complexity": 1, "files": ["app.py"], "acceptance_criteria": ["ok"], '
    '"depends_on": []}], "risks": [], "needs_collaboration": false}'
)
VERDICT = '{"approved": true, "issues": [], "summary": "ok"}'


def _service_config() -> HarnessConfig:
    return HarnessConfig.model_validate(
        {
            "models": {"default": {"provider": "fake", "name": "fake-model"}},
            "agents": [
                {"agent_id": "arch-1", "role": "architect", "model": "default"},
                {"agent_id": "mgr-1", "role": "manager", "model": "default"},
                {"agent_id": "ver-1", "role": "verifier", "model": "default"},
            ],
            "storage": {"backend": "memory"},
        }
    )


def _scripted_provider(fake_model_config):
    from harness.infrastructure.model_providers import FakeProvider, ModelResponse

    return FakeProvider(
        fake_model_config,
        responses=[
            ModelResponse(content=PROFILE),
            ModelResponse(content=PLAN),
            ModelResponse(content="TASK_COMPLETE: done"),
            ModelResponse(content=VERDICT),
        ],
    )


def test_health() -> None:
    app = create_app(config=_service_config(), provider=object())
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_analyze_endpoint(demo_repo: Path, fake_model_config) -> None:
    app = create_app(config=_service_config(), provider=_scripted_provider(fake_model_config))
    client = TestClient(app)
    response = client.post(
        "/agent/architect/analyze", json={"repo_root": str(demo_repo / "target")}
    )
    assert response.status_code == 200
    assert response.json()["profile"]["test_framework"] == "pytest"


def test_decompose_endpoint(demo_repo: Path, fake_model_config) -> None:
    app = create_app(config=_service_config(), provider=_scripted_provider(fake_model_config))
    client = TestClient(app)
    response = client.post(
        "/agent/architect/decompose",
        json={"issue": "greet works", "repo_root": str(demo_repo / "target")},
    )
    assert response.status_code == 200
    assert response.json()["plan"]["subtasks"][0]["id"] == "st-1"


def test_assign_and_status_endpoints(demo_repo: Path, fake_model_config) -> None:
    app = create_app(config=_service_config(), provider=_scripted_provider(fake_model_config))
    client = TestClient(app)
    response = client.post(
        "/agent/manager/assign",
        json={
            "task": {"id": "t-1", "title": "x", "description": "y"},
            "agent_id": "ver-1",
        },
    )
    assert response.status_code == 200 and response.json()["assigned"] is True
    # routing is bookkeeping: the manager reports idle until it executes
    status = client.get("/agent/status/mgr-1").json()
    assert status["known"] is True and status["status"] == "idle"
    unknown = client.get("/agent/status/ghost").json()
    assert unknown["known"] is False


def test_specialist_execute_endpoint(demo_repo: Path, fake_model_config) -> None:
    app = create_app(config=_service_config(), provider=_scripted_provider(fake_model_config))
    client = TestClient(app)
    response = client.post(
        "/agent/specialist/execute",
        json={
            "task": {"id": "t-9", "title": "t", "description": "d"},
        },
    )
    assert response.status_code == 200
    assert response.json()["result"]["task_id"] == "t-9"


def test_run_endpoint_publishes_redis_events(demo_repo: Path, fake_model_config) -> None:
    fake_redis = FakeRedis()
    app = create_app(
        config=_service_config(),
        provider=_scripted_provider(fake_model_config),
        redis_client=fake_redis,
    )
    client = TestClient(app)
    response = client.post(
        "/agent/run",
        json={
            "issue": "greet should work",
            "repo_root": str(demo_repo / "target"),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True and "VERIFIED" in body["outcome"]
    channels = {channel for channel, _ in fake_redis.published}
    assert any(channel.startswith("harness.events.") for channel in channels)
    payloads = [json.loads(message) for _, message in fake_redis.published]
    kinds = [p["event"] for p in payloads]
    assert "run.start" in kinds and "run.end" in kinds


def test_run_demo_mode_flag(demo_repo: Path, fake_model_config) -> None:
    app = create_app(config=_service_config(), provider=_scripted_provider(fake_model_config))
    client = TestClient(app)
    response = client.post(
        "/agent/run",
        json={
            "issue": "demo",
            "repo_root": str(demo_repo / "target"),
            "demo_mode": True,
        },
    )
    assert response.json()["success"] is True


def test_evidence_latest_endpoint(demo_repo: Path, fake_model_config) -> None:
    app = create_app(config=_service_config(), provider=_scripted_provider(fake_model_config))
    client = TestClient(app)
    client.post("/agent/run", json={"issue": "x", "repo_root": str(demo_repo / "target")})
    response = client.get("/evidence/latest", params={"repo_root": str(demo_repo / "target")})
    assert response.json()["found"] is True
    missing = client.get("/evidence/latest", params={"repo_root": str(demo_repo / "nope")})
    assert missing.json()["found"] is False


# -- publisher unit behavior (#72) ------------------------------------------------
def test_publisher_without_redis_is_noop() -> None:
    publisher = RedisEventPublisher()  # no client, no REDIS_URL
    publisher.publish("run-1", {"event": "x"})  # must not raise
    publisher.sink_for("run-1")({"event": "y"})


def test_publisher_publishes_json_envelope(fake_model_config) -> None:
    fake = FakeRedis()
    publisher = RedisEventPublisher(client=fake)
    publisher.sink_for("run-9")({"event": "run.start", "run_id": "run-9"})
    channel, message = fake.published[0]
    assert channel == "harness.events.run-9"
    assert json.loads(message)["event"] == "run.start"


def test_publisher_swallows_client_errors(fake_model_config) -> None:
    class ExplodingRedis:
        def publish(self, channel: str, message: str) -> int:
            raise RuntimeError("redis down")

    publisher = RedisEventPublisher(client=ExplodingRedis())
    publisher.publish("run-1", {"event": "x"})  # must not raise


def test_evidence_sink_exceptions_never_break_a_run(tmp_path: Path) -> None:
    """The event sink is best-effort: a raising sink is swallowed."""
    from harness.engine.evidence import EvidencePack

    def exploding(event: dict) -> None:
        raise RuntimeError("redis down")

    pack = EvidencePack(tmp_path, "run-sink", event_sink=exploding)
    pack.trace({"event": "x"})  # must not raise
    assert pack.read_trace()[0]["event"] == "x"


def test_config_lazy_load_when_none(monkeypatch, tmp_path: Path) -> None:
    """create_app(config=None) loads harness.yaml from cwd on first use."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "harness.yaml").write_text(
        "models:\n  default:\n    provider: fake\n    name: fake-model\n"
    )
    app = create_app(config=None, provider=object())
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    # the lazy config load triggers on any endpoint that needs the pipeline
    status = client.get("/agent/status/ver-1").json()
    assert status["known"] is False  # lazy config has no agents; load proven


def test_architect_fallback_when_config_has_no_architect(
    demo_repo: Path, fake_model_config
) -> None:
    config = HarnessConfig.model_validate(
        {
            "models": {"default": {"provider": "fake", "name": "fake-model"}},
            "agents": [{"agent_id": "ver-1", "role": "verifier", "model": "default"}],
            "storage": {"backend": "memory"},
        }
    )
    app = create_app(config=config, provider=_scripted_provider(fake_model_config))
    client = TestClient(app)
    response = client.post(
        "/agent/architect/analyze", json={"repo_root": str(demo_repo / "target")}
    )
    assert response.status_code == 200
    assert response.json()["profile"]["test_framework"] == "pytest"


def test_assign_without_manager_reports_absent(fake_model_config) -> None:
    config = HarnessConfig.model_validate(
        {
            "models": {"default": {"provider": "fake", "name": "fake-model"}},
            "agents": [{"agent_id": "ver-1", "role": "verifier", "model": "default"}],
            "storage": {"backend": "memory"},
        }
    )
    app = create_app(config=config, provider=_scripted_provider(fake_model_config))
    client = TestClient(app)
    response = client.post(
        "/agent/manager/assign",
        json={
            "task": {"id": "t-1", "title": "x", "description": "y"},
            "agent_id": "ver-1",
        },
    )
    assert response.json()["assigned"] is False
    assert "no manager configured" in response.json()["detail"]


def test_evidence_latest_without_runs(demo_repo: Path, fake_model_config) -> None:
    app = create_app(config=_service_config(), provider=_scripted_provider(fake_model_config))
    client = TestClient(app)
    (demo_repo / "target" / "results").mkdir()
    response = client.get("/evidence/latest", params={"repo_root": str(demo_repo / "target")})
    assert response.json()["found"] is False


def test_publisher_lazy_client_from_url(monkeypatch) -> None:
    """REDIS_URL set + no client: a real client is created lazily (faked here)."""
    import sys
    import types

    fake_module = types.ModuleType("redis")

    class FakeRedisClient:
        def __init__(self, url: str, decode_responses: bool = False) -> None:
            FakeRedisClient.url = url

        def publish(self, channel: str, message: str) -> int:
            return 1

    fake_module.Redis = types.SimpleNamespace(from_url=FakeRedisClient)
    monkeypatch.setitem(sys.modules, "redis", fake_module)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    publisher = RedisEventPublisher()  # no client -> lazy from REDIS_URL
    publisher.publish("run-lazy", {"event": "x"})
    assert FakeRedisClient.url == "redis://localhost:6379/0"
