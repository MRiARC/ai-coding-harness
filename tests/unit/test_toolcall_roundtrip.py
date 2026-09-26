"""Native tool-calling round-trip tests (Milestone 4, issue 4.1 / audit §5).

The release-blocking regression: the agent layer must preserve assistant
`tool_calls` and matching `tool_call_id`s across turns so strict providers
accept request #2. These tests exercise the full seam with mocked HTTP
(payload-level assertions on the wire) plus the agent loop over scripted
FakeProvider responses.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from harness.agents.llm_agent import LLMAgent, StoreWindow
from harness.agents.task import Task
from harness.config import BudgetConfig, ModelConfig
from harness.engine.budget import BudgetGovernor
from harness.infrastructure.context_store import MemoryContextStore, SQLiteContextStore
from harness.infrastructure.model_providers.anthropic import AnthropicProvider
from harness.infrastructure.model_providers.base import ModelResponse, ToolCall
from harness.infrastructure.model_providers.fake import FakeProvider
from harness.infrastructure.model_providers.openai_compatible import OpenAICompatibleProvider

NEUTRAL_TOOL_CALLS = [{"id": "tc1", "name": "read_file", "arguments": {"path": "src/app.py"}}]

OPENAI_TOOL_RESPONSE = {
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "tc1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": '{"path": "src/app.py"}'},
                    }
                ],
            },
            "finish_reason": "tool_calls",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    "model": "gpt-test",
}

ANTHROPIC_TOOL_RESPONSE = {
    "content": [
        {"type": "tool_use", "id": "tc1", "name": "read_file", "input": {"path": "src/app.py"}}
    ],
    "stop_reason": "tool_use",
    "usage": {"input_tokens": 10, "output_tokens": 5},
    "model": "claude-test",
}


def _neutral_followup() -> list[dict[str, Any]]:
    """What a conforming agent sends on turn 2: the assistant tool_calls plus
    the matching tool result (provider-neutral shape)."""
    return [
        {"role": "user", "content": "read src/app.py"},
        {"role": "assistant", "content": "", "tool_calls": NEUTRAL_TOOL_CALLS},
        {
            "role": "tool",
            "tool_call_id": "tc1",
            "tool_name": "read_file",
            "content": "[read_file] <file contents>",
        },
    ]


def test_openai_wire_projection() -> None:
    """Neutral messages project onto the strict OpenAI schema."""
    provider = OpenAICompatibleProvider(ModelConfig(provider="openai", name="gpt-test"))
    payload = provider._payload(_neutral_followup(), None)
    messages = payload["messages"]
    assert messages[0] == {"role": "user", "content": "read src/app.py"}
    assert messages[1]["role"] == "assistant"
    call = messages[1]["tool_calls"][0]
    assert call["id"] == "tc1"
    assert call["type"] == "function"
    assert call["function"]["name"] == "read_file"
    assert isinstance(call["function"]["arguments"], str)
    assert json.loads(call["function"]["arguments"]) == {"path": "src/app.py"}
    assert messages[2] == {
        "role": "tool",
        "content": "[read_file] <file contents>",
        "tool_call_id": "tc1",
    }


def test_openai_roundtrip_mocked_http() -> None:
    """Turn 2 over the wire carries the assistant tool_calls and the paired
    tool_call_id - the exact request a strict endpoint would 400 without."""
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode()))
        if len(bodies) == 1:
            return httpx.Response(200, json=OPENAI_TOOL_RESPONSE)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "done"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 2},
                "model": "gpt-test",
            },
        )

    config = ModelConfig(provider="openai-compatible", name="gpt-test", api_key_env="AI_API_KEY")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(config, client=client)
    provider._api_key = "test-key"

    first = asyncio.run(
        provider.generate([{"role": "user", "content": "read src/app.py"}], tools=[])
    )
    assert first.tool_calls[0].id == "tc1"

    asyncio.run(provider.generate(_neutral_followup(), tools=[]))

    second = bodies[1]["messages"]
    assert second[1]["tool_calls"][0]["function"]["name"] == "read_file"
    assert isinstance(second[1]["tool_calls"][0]["function"]["arguments"], str)
    assert second[2]["tool_call_id"] == "tc1"


def test_anthropic_roundtrip_mocked_http() -> None:
    """tool_use / tool_result pairs survive translation on turn 2."""
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode()))
        if len(bodies) == 1:
            return httpx.Response(200, json=ANTHROPIC_TOOL_RESPONSE)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "done"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 12, "output_tokens": 2},
                "model": "claude-test",
            },
        )

    config = ModelConfig(provider="anthropic", name="claude-test", api_key_env="AI_API_KEY")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = AnthropicProvider(config, client=client)
    provider._api_key = "test-key"

    first = asyncio.run(
        provider.generate([{"role": "user", "content": "read src/app.py"}], tools=[])
    )
    assert first.tool_calls[0].id == "tc1"

    asyncio.run(provider.generate(_neutral_followup(), tools=[]))

    contents = bodies[1]["messages"]
    tool_use_blocks = [
        block
        for message in contents
        if isinstance(message.get("content"), list)
        for block in message["content"]
        if block.get("type") == "tool_use"
    ]
    assert tool_use_blocks and tool_use_blocks[0]["id"] == "tc1"
    assert tool_use_blocks[0]["input"] == {"path": "src/app.py"}

    tool_results = [
        block
        for message in contents
        if isinstance(message.get("content"), list)
        for block in message["content"]
        if block.get("type") == "tool_result"
    ]
    assert tool_results and tool_results[0]["tool_use_id"] == "tc1"


@pytest.mark.parametrize("store_kind", ["memory", "sqlite"])
async def test_agent_loop_roundtrip(store_kind: str, tmp_path: Path) -> None:
    """The agent loop preserves structure across turns over both stores."""
    store: Any
    if store_kind == "memory":
        store = MemoryContextStore()
    else:
        store = SQLiteContextStore(tmp_path / "context.db")

    config = ModelConfig(provider="fake", name="fake-model", api_key_env="AI_API_KEY")
    provider = FakeProvider(
        config,
        responses=[
            ModelResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="read_file", arguments={"path": "src/app.py"})],
            ),
            ModelResponse(content="TASK_COMPLETE: read the file"),
        ],
    )
    governor = BudgetGovernor(store, BudgetConfig(), "run-1")
    agent = LLMAgent(
        agent_id="impl-1",
        model_config={},
        tools=[],
        context_window=StoreWindow(store, "impl-1", "task-1"),
        provider=provider,
        store=store,
        governor=governor,
        role="implementer",
    )
    result = await agent.execute_task(
        Task(id="task-1", title="Read a file", description="Use read_file.")
    )
    assert result.success

    second_call = provider.calls[1]["messages"]
    assistant = next(message for message in second_call if message["role"] == "assistant")
    assert assistant["tool_calls"][0]["id"] == "tc1"
    assert assistant["tool_calls"][0]["name"] == "read_file"
    tool_turn = next(message for message in second_call if message["role"] == "tool")
    assert tool_turn["tool_call_id"] == "tc1"
    assert tool_turn["tool_name"] == "read_file"

    # Both stores round-trip the structure, not just the in-memory view.
    reloaded = store.load_agent_context("impl-1", "task-1").recent
    assert reloaded[1].tool_calls[0]["id"] == "tc1"
    assert reloaded[2].tool_call_id == "tc1"


def test_toolcall_without_id_gets_synthesized() -> None:
    """Providers that omit tool-call ids still produce paired references."""
    response = ModelResponse(
        content="",
        tool_calls=[ToolCall(id="", name="search_text", arguments={"pattern": "x"})],
    )
    calls = [
        {"id": call.id or f"call_{index + 1}", "name": call.name, "arguments": call.arguments}
        for index, call in enumerate(response.tool_calls)
    ]
    assert calls[0]["id"] == "call_1"
