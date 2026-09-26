"""Milestone 4.7: budget governor modes control behavior (audit §13).

SURGICAL/FINALIZE are policies, not labels: the mode is injected into the
system prompt, re-planning is suppressed outside NORMAL, and dispatch is
reserved against the cap so the final call cannot overshoot.
"""

from __future__ import annotations

import pytest

from harness.agents.llm_agent import LLMAgent, StoreWindow
from harness.agents.task import Task, TaskResult
from harness.config import BudgetConfig, ModelConfig
from harness.engine.budget import BudgetExhausted, BudgetGovernor
from harness.engine.recovery import AttemptPolicy, RecoveryLadder
from harness.infrastructure.context_store import MemoryContextStore
from harness.infrastructure.model_providers.base import ModelResponse
from harness.infrastructure.model_providers.fake import FakeProvider
from harness.orchestration.messages import AgentStatus, ErrorEscalation, Severity, StatusUpdate


def _governor(store, used: int, total: int = 200_000) -> BudgetGovernor:
    governor = BudgetGovernor(
        store,
        BudgetConfig(total_tokens=total, warn_fraction=0.5, surgical_fraction=0.9),
        "run-1",
    )
    if used:
        governor.record("warmup", "fake-model", used, 0)
    return governor


def test_mode_thresholds_map_to_directives(memory_store) -> None:
    assert _governor(memory_store, used=10).mode().value == "normal"
    assert _governor(memory_store, used=150_000).mode().value == "surgical"
    assert _governor(memory_store, used=190_000).mode().value == "finalize"


async def test_surgical_mode_reaches_system_prompt(memory_store) -> None:
    config = ModelConfig(provider="fake", name="fake-model", api_key_env="AI_API_KEY")
    provider = FakeProvider(config, responses=[ModelResponse(content="done")])
    governor = _governor(memory_store, used=150_000)
    agent = LLMAgent(
        agent_id="impl-1",
        model_config={},
        tools=[],
        context_window=StoreWindow(memory_store, "impl-1", "task-1"),
        provider=provider,
        store=memory_store,
        governor=governor,
    )
    await agent.execute_task(Task(id="task-1", title="T", description="D"))
    system = provider.calls[0]["messages"][0]["content"]
    assert "BUDGET MODE surgical" in system


async def test_finalize_mode_reaches_system_prompt(memory_store) -> None:
    config = ModelConfig(provider="fake", name="fake-model", api_key_env="AI_API_KEY")
    provider = FakeProvider(config, responses=[ModelResponse(content="done")])
    governor = _governor(memory_store, used=190_000)
    agent = LLMAgent(
        agent_id="impl-1",
        model_config={},
        tools=[],
        context_window=StoreWindow(memory_store, "impl-1", "task-1"),
        provider=provider,
        store=memory_store,
        governor=governor,
    )
    await agent.execute_task(Task(id="task-1", title="T", description="D"))
    system = provider.calls[0]["messages"][0]["content"]
    assert "BUDGET MODE finalize-only" in system
    # NORMAL emits no directive at all
    config_normal = ModelConfig(provider="fake", name="fake-model", api_key_env="AI_API_KEY")
    provider_normal = FakeProvider(config_normal, responses=[ModelResponse(content="ok")])
    agent.governor = _governor(MemoryContextStore(), used=0)
    agent.provider = provider_normal
    await agent.execute_task(Task(id="task-2", title="T", description="D"))
    assert "BUDGET MODE" not in provider_normal.calls[0]["messages"][0]["content"]


def test_reserve_blocks_overshooting_dispatch(memory_store) -> None:
    governor = _governor(memory_store, used=45, total=50)
    governor.reserve(prompt_estimate=1, completion_reserve=1)  # 45+1+1 < 50 ok
    with pytest.raises(BudgetExhausted):
        governor.reserve(prompt_estimate=10)  # 45+10+1 >= 50 -> raises
    with pytest.raises(BudgetExhausted):
        governor.reserve(prompt_estimate=10)


def test_reserve_allows_headroom(memory_store) -> None:
    store = memory_store
    governor = BudgetGovernor(
        store,
        BudgetConfig(total_tokens=200_000, warn_fraction=0.5, surgical_fraction=0.9),
        "run-1",
    )
    governor.record("warmup", "m", 1000, 0)
    governor.reserve(prompt_estimate=5000)  # well inside
    assert governor.mode().value == "normal"


async def test_agent_stops_before_overshooting_call(memory_store) -> None:
    """With the cap nearly spent, the agent refuses the dispatch honestly."""
    config = ModelConfig(provider="fake", name="fake-model", api_key_env="AI_API_KEY")
    provider = FakeProvider(config, responses=[ModelResponse(content="never reached")])
    governor = _governor(memory_store, used=199_990, total=200_000)
    agent = LLMAgent(
        agent_id="impl-1",
        model_config={},
        tools=[],
        context_window=StoreWindow(memory_store, "impl-1", "task-1"),
        provider=provider,
        store=memory_store,
        governor=governor,
    )
    result = await agent.execute_task(Task(id="task-1", title="T", description="D"))
    assert not result.success
    assert "budget" in (result.error or "").lower()
    assert provider.calls == []  # dispatch refused before any model call


class StubManager:
    async def handle_escalation(self, escalation: ErrorEscalation) -> StatusUpdate:
        return StatusUpdate(sender="m", status=AgentStatus.WORKING, task_id=escalation.task_id)


class StubArchitect:
    def __init__(self) -> None:
        self.called = False

    async def reframe(self, task: Task, failure: str) -> Task:
        self.called = True
        return task


async def test_surgical_mode_suppresses_replan(memory_store) -> None:
    """L3 re-planning is skipped when the governor left NORMAL."""
    architect = StubArchitect()
    governor = _governor(memory_store, used=190_000)
    ladder = RecoveryLadder(
        StubManager(),
        architect,
        memory_store,
        policy=AttemptPolicy(self_repair=1, re_route=0, re_plan=1),
        governor=governor,
    )
    result = await ladder.run(
        Task(id="t-1", title="T", description="D"),
        _FailingExecutor(),
        _classify,
    )
    assert not result.success
    assert "budget governor" in (result.error or "")
    assert not architect.called


async def test_normal_mode_still_replans(memory_store) -> None:
    architect = StubArchitect()
    governor = _governor(memory_store, used=10)
    ladder = RecoveryLadder(
        StubManager(),
        architect,
        memory_store,
        policy=AttemptPolicy(self_repair=1, re_route=0, re_plan=1),
        governor=governor,
    )
    await ladder.run(Task(id="t-1", title="T", description="D"), _FailingExecutor(), _classify)
    assert architect.called


class _FailingExecutor:
    async def __call__(self, task: Task):
        return TaskResult(task_id=task.id, success=False, error="ValueError: boom")


async def _classify(task: Task, result: TaskResult) -> ErrorEscalation:
    return ErrorEscalation(
        sender="impl-1",
        task_id=task.id,
        severity=Severity.RECOVERABLE,
        error_type="ValueError",
        message="boom",
        attempt=1,
    )
