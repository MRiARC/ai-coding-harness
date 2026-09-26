"""Google provider: contents translation, payload, parsing (issue 1.5)."""

from __future__ import annotations

from harness.config import ModelConfig
from harness.infrastructure.model_providers.google import (
    GoogleProvider,
    _to_gemini_contents,
)

PROVIDER = GoogleProvider(ModelConfig(provider="google", name="gemini-x"))
MSGS = [{"role": "system", "content": "be terse"}, {"role": "user", "content": "fix parser.py"}]
TOOLS = [
    {
        "name": "read_file",
        "description": "read a file",
        "parameters": {"type": "object", "properties": {}},
    }
]


def test_system_instruction_and_contents() -> None:
    system, contents = _to_gemini_contents(MSGS)
    assert system == {"parts": [{"text": "be terse"}]}
    assert contents == [{"role": "user", "parts": [{"text": "fix parser.py"}]}]


def test_assistant_becomes_model_role_with_function_call() -> None:
    messages = [
        {
            "role": "assistant",
            "content": "reading",
            "tool_calls": [{"id": "t1", "name": "read_file", "arguments": {"path": "p"}}],
        },
        {"role": "tool", "tool_call_id": "t1", "name": "read_file", "content": "file body"},
    ]
    _, contents = _to_gemini_contents(messages)
    assert contents[0]["role"] == "model"
    assert contents[0]["parts"][0] == {"text": "reading"}
    assert contents[0]["parts"][1] == {"functionCall": {"name": "read_file", "args": {"path": "p"}}}
    assert contents[1]["parts"][0] == {
        "functionResponse": {"name": "read_file", "response": {"result": "file body"}}
    }


def test_payload_shape() -> None:
    payload = PROVIDER._payload(MSGS, TOOLS)
    assert payload["contents"][0]["role"] == "user"
    assert payload["systemInstruction"]["parts"] == [{"text": "be terse"}]
    assert payload["generationConfig"]["maxOutputTokens"] == 4096
    declaration = payload["tools"][0]["functionDeclarations"][0]
    assert declaration["name"] == "read_file" and "parameters" in declaration
    assert list(PROVIDER._headers("k").keys()) == ["x-goog-api-key", "Content-Type"]
    assert PROVIDER._endpoint() == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-x:generateContent"
    )


def test_parse_text_and_function_call() -> None:
    data = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "reading the file"},
                        {"functionCall": {"name": "read_file", "args": {"path": "p"}}},
                    ]
                },
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 15, "candidatesTokenCount": 4},
    }
    response = PROVIDER._parse_response(data, MSGS)
    assert response.content == "reading the file"
    assert response.tool_calls[0].arguments == {"path": "p"}
    assert (response.prompt_tokens, response.completion_tokens) == (15, 4)
    assert response.stop_reason == "STOP"


def test_parse_usage_fallback_estimates() -> None:
    response = PROVIDER._parse_response(
        {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}, MSGS
    )
    assert response.prompt_tokens > 0 and response.completion_tokens > 0
