"""Milestone 5 hardening (improvements §3.1): model capability probe and the
text-protocol fallback — the harness must run on models without native
tool calling (DeepSeek-Reasoner-style) and tolerate reasoning-model output
shapes (Qwen <think> blocks, None content)."""

from __future__ import annotations

from typing import Any, ClassVar

import httpx

from harness.agents.llm_agent import LLMAgent, StoreWindow
from harness.agents.task import Task
from harness.config import BudgetConfig, ModelConfig
from harness.engine.budget import BudgetGovernor
from harness.infrastructure.model_providers.base import ModelResponse
from harness.infrastructure.model_providers.capability import (
    CapabilityCache,
    ModelCapabilities,
    parse_tool_call_blocks,
    probe_capabilities,
    render_tool_manual,
    strip_think_blocks,
)
from harness.infrastructure.model_providers.fake import FakeProvider
from harness.infrastructure.model_providers.openai_compatible import (
    OpenAICompatibleProvider,
)
from harness.tools.base import Tool, ToolResult, ToolTier


class EchoTool(Tool):
    name, tier = "echo", ToolTier.BASIC
    description = "Echo the input back"
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
    }

    def __init__(self) -> None:
        self.seen: list[dict[str, Any]] = []

    def validate_input(self, arguments: dict[str, Any]) -> list[str]:
        return [] if "text" in arguments else ["'text' required"]

    def check_permissions(self, context: dict[str, Any]) -> bool:
        return True

    def execute(self, text: str = "", **_: Any) -> ToolResult:
        self.seen.append({"text": text})
        return ToolResult(success=True, output=f"echo: {text}")


def test_strip_think_blocks() -> None:
    assert strip_think_blocks("<think>pondering</think>final answer") == "final answer"
    assert strip_think_blocks("no blocks here") == "no blocks here"
    assert strip_think_blocks("<think>a</think>mid<think>b</think>end") == "midend"


def test_parse_tool_call_blocks_clean() -> None:
    text = 'Thinking...\nTOOL_CALL: {"name": "echo", "arguments": {"text": "hi"}}\n'
    calls = parse_tool_call_blocks(text)
    assert calls == [{"id": "", "name": "echo", "arguments": {"text": "hi"}}]


def test_parse_tool_call_blocks_fenced_and_multiple() -> None:
    text = (
        'plan:\n```json\nTOOL_CALL: {"name": "a", "arguments": {"x": 1}}\n```\n'
        'TOOL_CALL: {"name": "b", "arguments": {}}\n'
    )
    calls = parse_tool_call_blocks(text)
    assert [c["name"] for c in calls] == ["a", "b"]


def test_parse_tool_call_blocks_malformed_is_surfaced() -> None:
    calls = parse_tool_call_blocks("TOOL_CALL: {broken json")
    assert calls and calls[0]["arguments"].get("_unparsed")


def test_render_tool_manual_lists_tools_and_protocol() -> None:
    manual = render_tool_manual(
        [{"name": "echo", "description": "Echo", "parameters": {"type": "object"}}]
    )
    assert "- echo: Echo" in manual
    assert 'TOOL_CALL: {"name":' in manual


async def test_probe_detects_native_tool_calls() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "tc1",
                                    "type": "function",
                                    "function": {
                                        "name": "list_files",
                                        "arguments": '{"path": "."}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5},
                "model": "m",
            },
        )

    config = ModelConfig(provider="openai-compatible", name="m", api_key_env="AI_API_KEY")
    provider = OpenAICompatibleProbe(
        config, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    provider._api_key = "test-key"
    caps = await probe_capabilities(provider)
    assert caps.native_tool_calls is True


async def test_probe_detects_text_only_model() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "I would list files."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5},
                "model": "m",
            },
        )

    config = ModelConfig(provider="openai-compatible", name="m", api_key_env="AI_API_KEY")
    provider = OpenAICompatibleProbe(
        config, client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    provider._api_key = "test-key"
    caps = await probe_capabilities(provider)
    assert caps.native_tool_calls is False


async def test_probe_failure_is_optimistic() -> None:
    class Exploding:
        async def generate(self, *args: Any, **kwargs: Any) -> ModelResponse:
            raise RuntimeError("endpoint down")

    caps = await probe_capabilities(Exploding())  # type: ignore[arg-type]
    assert caps.native_tool_calls is True  # optimistic: pre-probe behavior
    assert "probe failed" in caps.detail


def test_capability_cache_roundtrip() -> None:
    cache = CapabilityCache()
    config = ModelConfig(provider="fake", name="m")
    provider = FakeProvider(config, responses=[])
    caps = ModelCapabilities(native_tool_calls=False, probed_at=1.0)
    assert cache.get(provider) is None
    cache.put(provider, caps)
    assert cache.get(provider) is caps


async def test_text_protocol_loop_executes_tools(memory_store) -> None:
    """A no-native-tools model still completes a task via TOOL_CALL text."""
    echo = EchoTool()
    config = ModelConfig(provider="fake", name="m", tool_call_mode="text")
    provider = FakeProvider(
        config,
        responses=[
            ModelResponse(
                content='I will use the tool.\nTOOL_CALL: {"name": "echo", "arguments": {"text": "hello"}}'
            ),
            ModelResponse(content="TASK_COMPLETE: echoed the text"),
        ],
    )
    provider.capabilities = ModelCapabilities(native_tool_calls=False)
    agent = LLMAgent(
        agent_id="impl-1",
        model_config={},
        tools=[echo],
        context_window=StoreWindow(memory_store, "impl-1", "task-1"),
        provider=provider,
        store=memory_store,
        governor=BudgetGovernor(memory_store, BudgetConfig(), "run-1"),
        role="implementer",
    )
    result = await agent.execute_task(Task(id="task-1", title="T", description="Echo something."))
    assert result.success
    assert echo.seen == [{"text": "hello"}]

    first_call = provider.calls[0]
    assert first_call["tools"] is None  # no native schemas sent
    system = first_call["messages"][0]["content"]
    assert "TOOL_CALL:" in system and "- echo:" in system  # manual rendered
    # results return as user turns (valid wire for text-only models)
    tool_results = [
        m
        for m in provider.calls[1]["messages"]
        if m["role"] == "user" and str(m.get("content", "")).startswith("TOOL_RESULT")
    ]
    assert tool_results and "echo: hello" in tool_results[0]["content"]


async def test_auto_mode_probes_once(memory_store) -> None:
    """auto: the probe runs once; later calls reuse the cached capability."""
    config = ModelConfig(provider="fake", name="probe-model", tool_call_mode="auto")
    provider = FakeProvider(
        config,
        responses=[
            ModelResponse(
                content="TASK_COMPLETE: native ok"
            ),  # probe sees marker text -> not native
            ModelResponse(content="TASK_COMPLETE: text protocol run"),
        ],
    )
    provider.capabilities = None  # force real probing against the script
    provider._api_key = "test-key"
    agent = LLMAgent(
        agent_id="impl-1",
        model_config={},
        tools=[],
        context_window=StoreWindow(memory_store, "impl-1", "task-1"),
        provider=provider,
        store=memory_store,
        governor=BudgetGovernor(memory_store, BudgetConfig(), "run-1"),
    )
    await agent.execute_task(Task(id="task-1", title="T", description="D"))
    assert provider.calls[1]["tools"] is None  # probe said text-only -> loop sends no schemas
    assert agent._capabilities is not None and agent._capabilities.native_tool_calls is False


def test_config_tool_call_mode_roundtrip() -> None:
    config = ModelConfig(provider="fake", name="m", tool_call_mode="text")
    assert config.tool_call_mode == "text"
    default = ModelConfig(provider="fake", name="m")
    assert default.tool_call_mode == "auto"


def test_parse_response_strips_think_blocks() -> None:
    from harness.infrastructure.model_providers.openai_compatible import OpenAICompatibleProvider

    provider = OpenAICompatibleProvider(ModelConfig(provider="openai", name="m"))
    parsed = provider._parse_response(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": '<think>chain of thought</think>TOOL_CALL: {"name": "echo"}',
                    }
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
        [],
    )
    assert "<think>" not in parsed.content
    assert "TOOL_CALL:" in parsed.content


class OpenAICompatibleProbe(OpenAICompatibleProvider):
    """Probe target with an injected client and pre-set key."""


async def test_native_mode_forces_native_without_probing(memory_store) -> None:
    """Explicit tool_call_mode: native skips the probe entirely."""
    config = ModelConfig(provider="fake", name="m", tool_call_mode="native")
    provider = FakeProvider(config, responses=[ModelResponse(content="TASK_COMPLETE: done")])
    agent = LLMAgent(
        agent_id="impl-1",
        model_config={},
        tools=[],
        context_window=StoreWindow(memory_store, "impl-1", "task-1"),
        provider=provider,
        store=memory_store,
        governor=BudgetGovernor(memory_store, BudgetConfig(), "run-1"),
    )
    assert await agent.native_tool_calls() is True
    assert agent._capabilities is None  # no probe call was made
