"""Token-diet tests (milestone 5: issues #61, #62, #63).

#61 stale tool-result stubbing in `StoreWindow.as_messages`; #62 deterministic
tool-call dedup + bounded loop nudge; #63 architect context diet (compact
repo summary + bounded structured-call windows).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pytest

from harness.agents.architect import ArchitectAgent
from harness.agents.llm_agent import (
    DEFAULT_KEEP_RECENT,
    LLMAgent,
    StoreWindow,
    compose_task_prompt,
)
from harness.agents.task import Task
from harness.config import AgentConfig, BudgetConfig, HarnessConfig, ModelConfig
from harness.engine.budget import BudgetGovernor
from harness.engine.pipeline import HarnessPipeline
from harness.infrastructure.context_store import MemoryContextStore
from harness.infrastructure.model_providers import FakeProvider, ModelResponse, ToolCall
from harness.tools.base import Tool, ToolResult, ToolTier
from harness.tools.filesystem import compact_repo_summary


class EchoTool(Tool):
    name, tier, description = "echo_tool", ToolTier.BASIC, "echo content back"
    parameters: ClassVar[dict] = {"type": "object", "properties": {"content": {"type": "string"}}}

    def __init__(self) -> None:
        self.calls = 0

    def validate_input(self, arguments: dict) -> list[str]:
        return []

    def check_permissions(self, context: dict) -> bool:
        return True

    def execute(self, content: str = "") -> ToolResult:
        self.calls += 1
        return ToolResult(success=True, output=f"echo: {content}")


class FakeReadTool(Tool):
    """Deterministic read tool named like the canonical registry entry (#62)."""

    name, tier, description = "filesystem_read", ToolTier.BASIC, "read a file"
    parameters: ClassVar[dict] = {"type": "object", "properties": {"path": {"type": "string"}}}

    def __init__(self) -> None:
        self.calls = 0

    def validate_input(self, arguments: dict) -> list[str]:
        return []

    def check_permissions(self, context: dict) -> bool:
        return True

    def execute(self, path: str = "", **_: Any) -> ToolResult:
        self.calls += 1
        return ToolResult(success=True, output=f"contents of {path}: " + "x" * 500)


class FakeEditTool(Tool):
    """Mutating tool named like the canonical registry entry (#62)."""

    name, tier, description = "apply_edit", ToolTier.DEVELOPMENT, "apply an edit"
    parameters: ClassVar[dict] = {"type": "object", "properties": {"path": {"type": "string"}}}

    def validate_input(self, arguments: dict) -> list[str]:
        return []

    def check_permissions(self, context: dict) -> bool:
        return True

    def execute(self, path: str = "", **_: Any) -> ToolResult:
        return ToolResult(success=True, output=f"edited {path}")


def _text(text: str) -> ModelResponse:
    return ModelResponse(content=text)


def _call(name: str, **arguments: str) -> ModelResponse:
    return ModelResponse(content="", tool_calls=[ToolCall(name=name, arguments=arguments)])


def _agent(
    store: MemoryContextStore,
    provider: FakeProvider,
    tools: list[Tool],
    *,
    keep_recent: int = DEFAULT_KEEP_RECENT,
) -> LLMAgent:
    governor = BudgetGovernor(store, BudgetConfig(total_tokens=1_000_000), "corr-diet")
    return LLMAgent(
        agent_id="agent-1",
        model_config={"provider": "fake"},
        tools=tools,
        context_window=StoreWindow(store, "agent-1", "t-1"),
        provider=provider,
        store=store,
        governor=governor,
        role="implementer",
        max_steps=8,
        keep_recent=keep_recent,
    )


def _architect(store: MemoryContextStore, provider: FakeProvider) -> ArchitectAgent:
    governor = BudgetGovernor(store, BudgetConfig(total_tokens=1_000_000), "corr-arch")
    return ArchitectAgent(
        agent_id="arch-1",
        model_config={"provider": "fake"},
        tools=[],
        context_window=StoreWindow(store, "arch-1", "planning"),
        provider=provider,
        store=store,
        governor=governor,
        role="architect",
    )


TASK = Task(id="t-1", title="do a thing", description="the thing")


# ---------------------------------------------------------------- #61 stale


def _window_with_tool_results(
    store: MemoryContextStore, n_tools: int, body_len: int = 300
) -> StoreWindow:
    window = StoreWindow(store, "agent-1", "t-1")
    window.append("user", "go")
    for i in range(n_tools):
        window.append(
            "assistant",
            "",
            tool_calls=[{"id": f"c{i}", "name": "filesystem_read", "arguments": {"path": "f.py"}}],
        )
        window.append(
            "tool",
            f"[filesystem_read] {'x' * body_len} part {i}",
            tool_call_id=f"c{i}",
            tool_name="filesystem_read",
        )
    return window


def test_stale_tool_results_stubbed_beyond_cutoff(store: MemoryContextStore) -> None:
    window = _window_with_tool_results(store, 8)
    window._stale_tool_results = 3
    messages = window.as_messages()
    tool_messages = [m for m in messages if m["role"] == "tool"]
    assert len(tool_messages) == 8
    stubbed = [m for m in tool_messages if "elided stale" in m["content"]]
    full = [m for m in tool_messages if "elided stale" not in m["content"]]
    assert len(stubbed) == 5
    assert len(full) == 3
    for message in stubbed:
        assert "filesystem_read" in message["content"]
        assert "chars" in message["content"]
        assert message["tool_call_id"] and message["tool_name"] == "filesystem_read"
    assert full[-1]["content"].endswith("part 7")


def test_stale_stub_leaves_non_tool_turns_untouched(store: MemoryContextStore) -> None:
    window = _window_with_tool_results(store, 8)
    window._stale_tool_results = 1
    messages = window.as_messages()
    assert messages[0] == {"role": "user", "content": "go"}
    assistants = [m for m in messages if m["role"] == "assistant"]
    assert all(m["content"] == "" for m in assistants)
    assert all(m["tool_calls"] for m in assistants)


def test_stale_stub_reduces_assembled_bytes(store: MemoryContextStore) -> None:
    window = _window_with_tool_results(store, 10, body_len=400)

    def tool_result_bytes(stale: int) -> int:
        window._stale_tool_results = stale
        return sum(len(m["content"]) for m in window.as_messages() if m["role"] == "tool")

    aggressive, baseline = tool_result_bytes(2), tool_result_bytes(1000)
    assert aggressive < 0.5 * baseline


def test_stale_zero_stubs_every_tool_turn(store: MemoryContextStore) -> None:
    window = _window_with_tool_results(store, 4)
    window._stale_tool_results = 0
    messages = window.as_messages()
    assert all("elided stale" in m["content"] for m in messages if m["role"] == "tool")


async def test_agent_plumbs_stale_tool_results(
    store: MemoryContextStore, fake_model_config: ModelConfig
) -> None:
    provider = FakeProvider(fake_model_config, responses=[_text("TASK_COMPLETE: done")])
    agent = _agent(store, provider, [EchoTool()])
    agent.stale_tool_results = 2
    result = await agent.execute_task(TASK)
    assert result.success
    assert isinstance(agent.context_window, StoreWindow)
    assert agent.context_window._stale_tool_results == 2


def test_agent_config_stale_tool_results_field() -> None:
    config = AgentConfig(agent_id="a-1", role="verifier", model="default", stale_tool_results=2)
    assert config.stale_tool_results == 2
    with pytest.raises(ValueError):  # pydantic wraps the ge=0 violation
        AgentConfig(agent_id="a-1", role="verifier", model="default", stale_tool_results=-1)


def test_pipeline_wires_stale_tool_results(tmp_path: Path) -> None:
    config = HarnessConfig.model_validate(
        {
            "models": {
                "default": {"provider": "fake", "name": "fake-model", "api_key_env": "AI_API_KEY"}
            },
            "agents": [
                {
                    "agent_id": "arch-1",
                    "role": "architect",
                    "model": "default",
                    "stale_tool_results": 2,
                },
                {
                    "agent_id": "ver-1",
                    "role": "verifier",
                    "model": "default",
                    "stale_tool_results": 3,
                },
            ],
        }
    )
    provider = FakeProvider(config.models["default"], responses=[])
    pipeline = HarnessPipeline(tmp_path, config, provider, MemoryContextStore())
    assert pipeline._architect is not None
    assert pipeline._architect.context_window._stale_tool_results == 2  # type: ignore[union-attr]
    specialist = next(a for a in pipeline._agents.values() if a.role == "verifier")
    assert specialist.stale_tool_results == 3


# ---------------------------------------------------------------- #62 dedup


async def test_dedup_cache_hit_skips_execution(
    store: MemoryContextStore, fake_model_config: ModelConfig
) -> None:
    tool = FakeReadTool()
    provider = FakeProvider(
        fake_model_config,
        responses=[
            _call("filesystem_read", path="a.py"),
            _call("filesystem_read", path="a.py"),
            _text("TASK_COMPLETE: done"),
        ],
    )
    agent = _agent(store, provider, [tool])
    result = await agent.execute_task(TASK)
    assert result.success
    assert tool.calls == 1
    window_content = [t.content for t in store.load_agent_context("agent-1", "t-1").recent]
    assert any("[dedup:" in c for c in window_content)


async def test_dedup_invalidated_by_apply_edit(
    store: MemoryContextStore, fake_model_config: ModelConfig
) -> None:
    read_tool, edit_tool = FakeReadTool(), FakeEditTool()
    provider = FakeProvider(
        fake_model_config,
        responses=[
            _call("filesystem_read", path="a.py"),
            _call("apply_edit", path="a.py"),
            _call("filesystem_read", path="a.py"),
            _text("TASK_COMPLETE: done"),
        ],
    )
    agent = _agent(store, provider, [read_tool, edit_tool])
    result = await agent.execute_task(TASK)
    assert result.success
    assert read_tool.calls == 2


async def test_dedup_never_applies_to_non_deterministic_tools(
    store: MemoryContextStore, fake_model_config: ModelConfig
) -> None:
    tool = EchoTool()
    provider = FakeProvider(
        fake_model_config,
        responses=[
            _call("echo_tool", content="a"),
            _call("echo_tool", content="a"),
            _text("TASK_COMPLETE: done"),
        ],
    )
    agent = _agent(store, provider, [tool])
    result = await agent.execute_task(TASK)
    assert result.success
    assert tool.calls == 2


async def test_loop_nudge_after_repeated_identical_calls(
    store: MemoryContextStore, fake_model_config: ModelConfig
) -> None:
    tool = FakeReadTool()
    provider = FakeProvider(
        fake_model_config,
        responses=[
            _call("filesystem_read", path="a.py"),
            _call("filesystem_read", path="a.py"),
            _call("filesystem_read", path="a.py"),
            _text("TASK_COMPLETE: gave up on the loop"),
        ],
    )
    agent = _agent(store, provider, [tool])
    result = await agent.execute_task(TASK)
    assert result.success
    turns = store.load_agent_context("agent-1", "t-1").recent
    nudges = [t for t in turns if t.role == "user" and "Loop detected" in t.content]
    assert len(nudges) == 1
    assert tool.calls == 1


async def test_loop_nudges_are_bounded(
    store: MemoryContextStore, fake_model_config: ModelConfig
) -> None:
    tool = FakeReadTool()
    provider = FakeProvider(
        fake_model_config,
        responses=[_call("filesystem_read", path="a.py") for _ in range(6)]
        + [_text("TASK_COMPLETE: done")],
    )
    agent = _agent(store, provider, [tool])
    result = await agent.execute_task(TASK)
    assert result.success
    turns = store.load_agent_context("agent-1", "t-1").recent
    nudges = [t for t in turns if t.role == "user" and "Loop detected" in t.content]
    assert len(nudges) == 2  # MAX_UNMARKED_NUDGES


async def test_dedup_state_resets_between_tasks(
    store: MemoryContextStore, fake_model_config: ModelConfig
) -> None:
    tool = FakeReadTool()
    provider = FakeProvider(
        fake_model_config,
        responses=[
            _call("filesystem_read", path="a.py"),
            _text("TASK_COMPLETE: first"),
            _call("filesystem_read", path="a.py"),
            _text("TASK_COMPLETE: second"),
        ],
    )
    agent = _agent(store, provider, [tool])
    first = await agent.execute_task(TASK)
    second = await agent.execute_task(Task(id="t-2", title="again", description="again"))
    assert first.success and second.success
    assert tool.calls == 2


# ---------------------------------------------------------------- #63 diet


def test_compact_repo_summary_drops_empty_fields() -> None:
    text = compact_repo_summary({"languages": ["Python"], "frameworks": [], "notes": ""})
    assert '"languages"' in text
    assert "frameworks" not in text
    assert "notes" not in text


def test_compact_repo_summary_truncates_with_marker() -> None:
    text = compact_repo_summary({"big": "y" * 10_000}, max_chars=100)
    assert len(text) < 200
    assert "repo summary truncated at 100 chars" in text


async def test_architect_analyze_uses_compact_summary(
    store: MemoryContextStore, fake_model_config: ModelConfig
) -> None:
    provider = FakeProvider(
        fake_model_config,
        responses=[
            _text(
                '{"languages": ["Python"], "frameworks": [], "test_framework": "pytest", '
                '"build_system": "pyproject.toml", "conventions": [], "notes": "n"}'
            )
        ],
    )
    architect = _architect(store, provider)
    profile = await architect.analyze_repository(
        {"languages": [], "frameworks": [], "total_files": 3, "notes": ""}
    )
    assert profile.languages == ["Python"]
    prompt = str(provider.calls[0]["messages"][1]["content"])
    assert "total_files" in prompt
    assert '"languages"' not in prompt  # empty field dropped before serialization


async def test_structured_call_compresses_window(
    store: MemoryContextStore, fake_model_config: ModelConfig
) -> None:
    provider = FakeProvider(fake_model_config, responses=[_text('{"approved": true}')])
    architect = _architect(store, provider)
    architect.keep_recent = 4
    for i in range(3):  # pre-populate the planning window
        architect.context_window.append("user", f"old turn {i}")
    parsed = await architect.structured_call("inst", "user prompt", '{"approved": bool}')
    assert parsed == {"approved": True}
    context = store.load_agent_context("arch-1", "planning")
    # 3 old + user + assistant = 5 >= keep_recent 4 -> folded
    assert len(context.recent) <= 3
    assert context.summary


async def test_structured_call_without_task_id_window_skips_compression(
    store: MemoryContextStore, fake_model_config: ModelConfig
) -> None:
    class BareWindow:
        def append(self, role: str, content: str) -> None:
            pass

        def as_messages(self) -> list[dict[str, Any]]:
            return []

    provider = FakeProvider(fake_model_config, responses=[_text('{"approved": true}')])
    architect = _architect(store, provider)
    architect.context_window = BareWindow()  # type: ignore[assignment]
    parsed = await architect.structured_call("inst", "user prompt", '{"approved": bool}')
    assert parsed == {"approved": True}


def test_compose_task_prompt_capped_sections() -> None:
    task = Task(
        id="t-9",
        title="big",
        description="d",
        acceptance_criteria=[c * 300 for c in "abcdefghijk"],
        files=[f"f{i}.py" for i in range(20)],
        metadata={"guidance": "g" * 1000},
    )
    prompt = compose_task_prompt(task)
    assert "EXPECTED FILES: " in prompt
    assert len([ln for ln in prompt.splitlines() if ln.startswith("- ")]) == 10
    assert "g" * 601 not in prompt
