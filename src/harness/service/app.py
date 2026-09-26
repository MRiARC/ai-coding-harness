"""Python Agent Orchestrator service (platform P1, issue #70).

FastAPI wrapper around the proven engine: exposes the
TECHNICAL_IMPLEMENTATION.md §2.2 endpoints (architect analyze/decompose,
manager assign, specialist execute, status) plus `/agent/run` (full
pipeline) and `/health`. The graded core never imports this module - it
is an optional `harness[platform]` add-on.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from harness import __version__
from harness.config import HarnessConfig
from harness.engine.evidence import EvidencePack
from harness.engine.pipeline import HarnessPipeline
from harness.infrastructure.context_store import create_context_store
from harness.infrastructure.model_providers import create_model_provider
from harness.service.events import RedisEventPublisher


class AnalyzeRequest(BaseModel):
    repo_root: str = Field(min_length=1)


class DecomposeRequest(BaseModel):
    issue: str = Field(min_length=1)
    repo_root: str = Field(min_length=1)


class AssignRequest(BaseModel):
    task: dict[str, Any]
    agent_id: str = Field(min_length=1)


class ExecuteRequest(BaseModel):
    task: dict[str, Any]


class RunRequest(BaseModel):
    issue: str = Field(min_length=1)
    repo_root: str = "."
    demo_mode: bool = False


def create_app(
    config: HarnessConfig | None = None,
    provider: Any = None,
    redis_client: Any = None,
) -> FastAPI:
    """Build the orchestrator app.

    `provider`/`redis_client` are injection seams for tests; production
    builds the configured model provider and reads REDIS_URL.
    """
    app = FastAPI(title="Foreman Agent Orchestrator", version=__version__)
    resolved_config = config
    publisher = RedisEventPublisher(client=redis_client)

    def _config() -> HarnessConfig:
        nonlocal resolved_config
        if resolved_config is None:
            from harness.config import load_config

            resolved_config = load_config()
        return resolved_config

    def _pipeline(repo_root: str, event_sink: Any = None) -> HarnessPipeline:
        cfg = _config()
        store = create_context_store(cfg.storage)
        resolved = provider or create_model_provider(cfg.models["default"])
        return HarnessPipeline(
            repo_root=repo_root, config=cfg, provider=resolved, store=store,
            event_sink=event_sink,
        )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "service": "orchestrator", "version": __version__}

    @app.post("/agent/architect/analyze")
    async def analyze(request: AnalyzeRequest) -> dict[str, Any]:
        from harness.tools.filesystem import summarize_repository

        pipeline = _pipeline(request.repo_root)
        architect = pipeline._architect  # noqa: SLF001 - same-package service seam
        if architect is None:
            from harness.agents.architect import build_architect

            architect = build_architect(
                "orchestrator-architect", {"provider": "service"},
                pipeline._provider, pipeline._store,  # noqa: SLF001
            )
        profile = await architect.analyze_repository(
            summarize_repository(pipeline._repo_root)  # noqa: SLF001
        )
        return {"profile": profile.model_dump()}

    @app.post("/agent/architect/decompose")
    async def decompose(request: DecomposeRequest) -> dict[str, Any]:
        from harness.tools.filesystem import summarize_repository

        pipeline = _pipeline(request.repo_root)
        architect = pipeline._architect  # noqa: SLF001
        if architect is None:
            from harness.agents.architect import build_architect

            architect = build_architect(
                "orchestrator-architect", {"provider": "service"},
                pipeline._provider, pipeline._store,  # noqa: SLF001
            )
        plan = await architect.decompose(
            request.issue,
            await architect.analyze_repository(
                summarize_repository(pipeline._repo_root)  # noqa: SLF001
            ),
        )
        return {"plan": plan.model_dump()}

    @app.post("/agent/manager/assign")
    async def assign(request: AssignRequest) -> dict[str, Any]:
        pipeline = _pipeline(".")
        manager = pipeline._manager  # noqa: SLF001
        if manager is None:
            from harness.agents.task import Task

            task = Task.model_validate(request.task)
            manager = pipeline._agents.get("mgr-1")
            if manager is None:
                return {"assigned": False, "detail": "no manager configured"}
            await manager.assign_task(task, request.agent_id)
            return {"assigned": True, "task": task.id, "agent": request.agent_id}
        from harness.agents.task import Task

        task = Task.model_validate(request.task)
        await manager.assign_task(task, request.agent_id)
        return {"assigned": True, "task": task.id, "agent": request.agent_id}

    @app.post("/agent/specialist/execute")
    async def execute(request: ExecuteRequest) -> dict[str, Any]:
        from harness.agents.task import Task

        task = Task.model_validate(request.task)
        pipeline = _pipeline(".")
        agent_id, agent = next(iter(pipeline._agents.items()))  # noqa: SLF001
        result = await agent.execute_task(task)
        return {"result": result.model_dump(), "agent": agent_id}

    @app.get("/agent/status/{agent_id}")
    async def status(agent_id: str) -> dict[str, Any]:
        pipeline = _pipeline(".")
        agent = pipeline._agents.get(agent_id)  # noqa: SLF001
        if agent is None:
            return {"agent_id": agent_id, "known": False}
        update = agent.report_status()
        return {"agent_id": agent_id, "known": True,
                "status": update.status.value, "task_id": update.task_id}

    @app.post("/agent/run")
    async def run(request: RunRequest) -> dict[str, Any]:
        import uuid

        run_id = uuid.uuid4().hex[:12]
        pipeline = _pipeline(request.repo_root,
                             event_sink=publisher.sink_for(run_id))
        outcome = await pipeline.run(request.issue, demo_mode=request.demo_mode)
        return {
            "run_id": outcome.run_id,
            "success": outcome.success,
            "outcome": outcome.outcome_line,
            "evidence_path": str(outcome.evidence_path),
            "flags": outcome.flags,
        }

    @app.get("/evidence/latest")
    async def evidence_latest(repo_root: str = ".") -> dict[str, Any]:
        results = _config().run.results_dir
        from pathlib import Path

        root = Path(repo_root) / results
        if not root.is_dir():
            return {"found": False}
        runs = sorted((d for d in root.iterdir() if d.is_dir()),
                      key=lambda d: d.stat().st_mtime, reverse=True)
        pack = EvidencePack(root, runs[0].name) if runs else None
        return {"found": pack is not None,
                "run_id": pack.run_id if pack else None,
                "path": str(pack.path) if pack else None}

    return app
