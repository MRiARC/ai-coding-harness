"""Anthropic provider: message translation, payload, parsing (issue 1.5)."""

from __future__ import annotations

from harness.config import ModelConfig
from harness.infrastructure.model_providers.anthropic import (
    AnthropicProvider,
    _to_anthropic_messages,
)

PROVIDER = AnthropicProvider(ModelConfig(provider="anthropic", name="claude-x"))
MSGS = [{"role": "system", "content": "be terse"}, {"role": "user", "content": "fix parser.py"}]
TOOLS = [
    {
        "name": "read_file",
        "description": "read a file",
        "parameters": {"type": "object", "properties": {}},
    }
]


def test_system_extracted_and_plain_messages() -> None:
    system, messages = _to_anthropic_messages(MSGS)
    assert system == "be terse"
    assert messages == [{"role": "user", "content": "fix parser.py"}]


def test_tool_calls_and_tool_results_translated() -> None:
    messages = [
        {
            "role": "assistant",
            "content": "reading",
            "tool_calls": [{"id": "t1", "name": "read_file", "arguments": {"path": "p"}}],
        },
        {"role": "tool", "tool_call_id": "t1", "content": "file body"},
    ]
    _, out = _to_anthropic_messages(messages)
    assert out[0]["content"][0] == {"type": "text", "text": "reading"}
    assert out[0]["content"][1] == {
        "type": "tool_use",
        "id": "t1",
        "name": "read_file",
        "input": {"path": "p"},
    }
    assert out[1]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "t1",
        "content": "file body",
    }


def test_payload_uses_messages_api_shape() -> None:
    payload = PROVIDER._payload(MSGS, TOOLS)
    assert payload["model"] == "claude-x"
    assert payload["system"] == "be terse"
    assert payload["max_tokens"] == 4096
    assert payload["tools"][0]["input_schema"] == {"type": "object", "properties": {}}
    assert "x-api-key" in PROVIDER._headers("k")
    assert PROVIDER._endpoint() == "https://api.anthropic.com/v1/messages"


def test_parse_text_and_tool_use() -> None:
    data = {
        "content": [
            {"type": "text", "text": "reading the file"},
            {"type": "tool_use", "id": "t1", "name": "read_file", "input": {"path": "p"}},
        ],
        "usage": {"input_tokens": 12, "output_tokens": 3},
        "stop_reason": "tool_use",
        "model": "claude-x",
    }
    response = PROVIDER._parse_response(data, MSGS)
    assert response.content == "reading the file"
    assert response.tool_calls[0].arguments == {"path": "p"}
    assert (response.prompt_tokens, response.completion_tokens) == (12, 3)
    assert response.stop_reason == "tool_use"


def test_parse_usage_fallback_estimates() -> None:
    data = {"content": [{"type": "text", "text": "hello"}]}
    response = PROVIDER._parse_response(data, MSGS)
    assert response.prompt_tokens > 0 and response.completion_tokens > 0


def test_base_url_override() -> None:
    provider = AnthropicProvider(
        ModelConfig(provider="anthropic", name="c", base_url="https://proxy.internal")
    )
    assert provider._endpoint() == "https://proxy.internal/v1/messages"
