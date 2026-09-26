"""Milestone 4.2 + 4.3: per-task context rebinding and full task prompts.

Audit §10: an agent's conversation window must be rebound to the active task
(sequential tasks must not share or split context) and the task text must be
present in the first model call. Audit §9: acceptance criteria, expected
files, required tools, and Manager guidance must reach the model.
"""

from __future__ import annotations

from harness.agents.llm_agent import LLMAgent, StoreWindow, compose_task_prompt
from harness.agents.task import Task
from harness.config import BudgetConfig, ModelConfig
from harness.engine.budget import BudgetGovernor
from harness.infrastructure.model_providers.base import ModelResponse
from harness.infrastructure.model_providers.fake import FakeProvider


def _make_agent(
    store, role: str = "implementer", responses: int = 1
) -> tuple[LLMAgent, FakeProvider]:
    config = ModelConfig(provider="fake", name="fake-model", api_key_env="AI_API_KEY")
    provider = FakeProvider(
        config, responses=[ModelResponse(content="TASK_COMPLETE: done") for _ in range(responses)]
    )
    governor = BudgetGovernor(store, BudgetConfig(), "run-1")
    agent = LLMAgent(
        agent_id="impl-1",
        model_config={},
        tools=[],
        context_window=StoreWindow(store, "impl-1", "ad-hoc"),
        provider=provider,
        store=store,
        governor=governor,
        role=role,
    )
    return agent, provider


async def test_window_rebinds_to_active_task(memory_store) -> None:
    """Sequential tasks get separate windows; each first call sees its text."""
    agent, provider = _make_agent(memory_store, responses=2)
    first = Task(id="task-1", title="First task", description="Do the first thing.")
    second = Task(id="task-2", title="Second task", description="Do the second thing.")

    await agent.execute_task(first)
    await agent.execute_task(second)

    # The agent was constructed with an "ad-hoc" window; execution rebinds.
    assert agent.context_window._task_id == "task-2"

    first_call_messages = provider.calls[0]["messages"]
    assert any("Do the first thing." in str(m.get("content")) for m in first_call_messages)
    second_call_messages = provider.calls[1]["messages"]
    assert any("Do the second thing." in str(m.get("content")) for m in second_call_messages)
    # No bleed: the second call must not replay the first task's window.
    assert not any("Do the first thing." in str(m.get("content")) for m in second_call_messages)


async def test_first_call_contains_task_text(sqlite_store) -> None:
    """The store-backed window includes the TASK line on model call 1."""
    agent, provider = _make_agent(sqlite_store)
    await agent.execute_task(
        Task(id="t-1", title="Fix bug", description="The parser crashes on empty input.")
    )
    messages = provider.calls[0]["messages"]
    user_messages = [m for m in messages if m["role"] == "user"]
    assert user_messages and "parser crashes on empty input" in str(user_messages[0]["content"])


def test_compose_task_prompt_includes_all_fields() -> None:
    """Audit §9: criteria, files, tools, and guidance reach the prompt."""
    task = Task(
        id="t-1",
        title="Add endpoint",
        description="Implement the export endpoint.",
        acceptance_criteria=["returns 200", "handles empty payload"],
        specialty="backend-api",
        required_tools=["read_file", "apply_edit"],
        files=["src/api.py", "tests/test_api.py"],
        metadata={"guidance": "reuse the existing auth middleware"},
    )
    prompt = compose_task_prompt(task)
    assert "TASK: Add endpoint" in prompt
    assert "Implement the export endpoint." in prompt
    assert "- returns 200" in prompt
    assert "- handles empty payload" in prompt
    assert "EXPECTED FILES: src/api.py, tests/test_api.py" in prompt
    assert "REQUIRED TOOLS: read_file, apply_edit" in prompt
    assert "MANAGER GUIDANCE: reuse the existing auth middleware" in prompt


def test_compose_task_prompt_sections_absent_when_empty() -> None:
    task = Task(id="t-2", title="Minimal", description="Nothing extra.")
    prompt = compose_task_prompt(task)
    assert "ACCEPTANCE CRITERIA" not in prompt
    assert "EXPECTED FILES" not in prompt
    assert "REQUIRED TOOLS" not in prompt
    assert "MANAGER GUIDANCE" not in prompt


def test_compose_task_prompt_caps_oversized_sections() -> None:
    """Observation compression: criteria/guidance are bounded, not unbounded."""
    task = Task(
        id="t-3",
        title="Big",
        description="x" * 10,
        acceptance_criteria=[f"criterion {i} " + "y" * 300 for i in range(20)],
        metadata={"guidance": "g" * 2000},
    )
    prompt = compose_task_prompt(task)
    assert len(prompt) < 5000  # 20 x 300-char criteria would be ~6k alone
    assert prompt.count("criterion") == 10  # only the first 10 kept
    assert "MANAGER GUIDANCE" in prompt


def test_compose_task_prompt_via_agent_execute(memory_store) -> None:
    """End to end: a task with fields produces a prompt carrying them."""
    agent, provider = _make_agent(memory_store)
    task = Task(
        id="t-9",
        title="Task with fields",
        description="body",
        acceptance_criteria=["works"],
        metadata={"guidance": "be careful"},
    )
    import asyncio

    asyncio.run(agent.execute_task(task))
    first_user = next(m for m in provider.calls[0]["messages"] if m["role"] == "user")
    content = str(first_user["content"])
    assert "ACCEPTANCE CRITERIA" in content and "- works" in content
    assert "MANAGER GUIDANCE: be careful" in content
