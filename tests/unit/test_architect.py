"""Architect agent tests: analyze, decompose, review, reframe (issues 2.1-2.3)."""

from __future__ import annotations

import pytest

from harness.agents.architect import ArchitectAgent, Plan, SubTask, build_architect
from harness.agents.llm_agent import StoreWindow, StructuredOutputError
from harness.agents.task import Task
from harness.config import BudgetConfig
from harness.engine.budget import BudgetGovernor
from harness.infrastructure.context_store import MemoryContextStore
from harness.infrastructure.model_providers import FakeProvider, ModelResponse

REPO_SUMMARY = {
    "languages": ["Python"],
    "test_files": 12,
    "build_system": "pyproject.toml",
}


@pytest.fixture
def store() -> MemoryContextStore:
    return MemoryContextStore()


def _agent(store: MemoryContextStore, provider: FakeProvider) -> ArchitectAgent:
    governor = BudgetGovernor(store, BudgetConfig(total_tokens=100_000), "corr-arch")
    return ArchitectAgent(
        agent_id="arch-1",
        model_config={"provider": "fake"},
        tools=[],
        context_window=StoreWindow(store, "arch-1", "planning"),
        provider=provider,
        store=store,
        governor=governor,
    )


async def test_analyze_repository_saves_global_profile(store, fake_model_config) -> None:
    provider = FakeProvider(
        fake_model_config,
        responses=[
            ModelResponse(
                content='{"languages": ["Python"], "test_framework": "pytest", '
                '"build_system": "pyproject.toml", "conventions": ["typed"], '
                '"frameworks": ["pydantic"], "notes": "clean"}'
            ),
        ],
    )
    agent = _agent(store, provider)
    profile = await agent.analyze_repository(REPO_SUMMARY)
    assert profile.test_framework == "pytest"
    assert store.load_global("repo_profile")["languages"] == ["Python"]


async def test_analyze_repairs_malformed_json(store, fake_model_config) -> None:
    provider = FakeProvider(
        fake_model_config,
        responses=[
            ModelResponse(content="I think it's Python, not JSON."),
            ModelResponse(content='{"languages": ["Python"], "notes": "ok"}'),
        ],
    )
    profile = await _agent(store, provider).analyze_repository(REPO_SUMMARY)
    assert profile.languages == ["Python"]
    assert len(provider.calls) == 2


async def test_analyze_fails_after_repair(store, fake_model_config) -> None:
    provider = FakeProvider(
        fake_model_config,
        responses=[
            ModelResponse(content="nope"),
            ModelResponse(content="still nope"),
        ],
    )
    with pytest.raises(StructuredOutputError):
        await _agent(store, provider).analyze_repository(REPO_SUMMARY)


async def test_decompose_builds_plan(store, fake_model_config) -> None:
    provider = FakeProvider(
        fake_model_config,
        responses=[
            ModelResponse(
                content=(
                    '{"issue_summary": "parser crashes", "complexity": 4, '
                    '"subtasks": [{"id": "st-1", "title": "fix guard", "description": "add empty check", '
                    '"specialty": "backend-api", "complexity": 3, "files": ["src/parser.py"], '
                    '"acceptance_criteria": ["no crash on empty"], "depends_on": []}], '
                    '"risks": ["regressions"], "needs_collaboration": false}'
                )
            ),
            ModelResponse(content='{"issue_summary": "second", "complexity": 2, "subtasks": []}'),
        ],
    )
    agent = _agent(store, provider)
    plan = await agent.decompose("parser crashes on empty input")
    assert plan.subtasks[0].files == ["src/parser.py"]
    assert store.load_global("plan")["complexity"] == 4
    # decompose without a profile also works (no profile section in the prompt)
    plan2 = await agent.decompose("another issue", profile=None)
    assert plan2.subtasks == []


async def test_review_approves_or_flags(store, fake_model_config) -> None:
    provider = FakeProvider(
        fake_model_config,
        responses=[
            ModelResponse(
                content='{"approved": false, "issues": ["empty check missing"], '
                '"summary": "needs work"}'
            ),
        ],
    )
    agent = _agent(store, provider)
    plan = Plan(
        issue_summary="s",
        subtasks=[SubTask(id="st-1", title="t", description="d", acceptance_criteria=["no crash"])],
    )
    verdict = await agent.review("diff --git a/parser.py ...", plan)
    assert not verdict.approved and "empty check missing" in verdict.issues


async def test_reframe_rewrites_task(store, fake_model_config) -> None:
    provider = FakeProvider(
        fake_model_config,
        responses=[
            ModelResponse(
                content='{"title": "add empty-input guard", '
                '"description": "one-line check", "acceptance_criteria": ["passes"]}'
            ),
        ],
    )
    agent = _agent(store, provider)
    task = Task(id="t-1", title="fix parser", description="vague")
    reframed = await agent.reframe(task, "ValueError: kept failing")
    assert reframed.title == "add empty-input guard"
    assert reframed.metadata["reframed"] is True


async def test_reframe_falls_back_to_original_fields(store, fake_model_config) -> None:
    provider = FakeProvider(
        fake_model_config,
        responses=[
            ModelResponse(content='{"unrelated": true}'),
        ],
    )
    task = Task(id="t-1", title="keep me", description="d", acceptance_criteria=["a"])
    reframed = await _agent(store, provider).reframe(task, "err")
    assert reframed.title == "keep me" and reframed.acceptance_criteria == ["a"]


def test_subtask_to_task_mapping() -> None:
    subtask = SubTask(
        id="st-9",
        title="t",
        description="d",
        specialty="testing",
        complexity=6,
        files=["a.py"],
        acceptance_criteria=["x"],
        depends_on=["st-1"],
    )
    task = subtask.to_task()
    assert task.specialty == "testing" and task.metadata["depends_on"] == ["st-1"]


def test_build_architect_factory(store, fake_model_config) -> None:
    governor = BudgetGovernor(store, BudgetConfig(total_tokens=1000), "c")
    agent = build_architect(
        "arch-x", {"provider": "fake"}, FakeProvider(fake_model_config, []), store, governor
    )
    assert agent.role == "architect" and agent.agent_id == "arch-x"
