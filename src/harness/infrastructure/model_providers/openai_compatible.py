"""OpenAI / OpenAI-compatible provider (chat completions API)."""

from __future__ import annotations

import json
from typing import Any

from harness.infrastructure.model_providers.base import (
    ModelProvider,
    ModelResponse,
    ToolCall,
    _approx_tokens,
)


def _safe_json(raw: str | dict[str, Any]) -> dict[str, Any]:
    """Parse model-emitted tool arguments tolerantly (never raise on bad JSON)."""
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.JSONDecodeError:
        return {"_raw": str(raw)}


class OpenAICompatibleProvider(ModelProvider):
    """Works with OpenAI and any compatible endpoint (the default eval provider).

    Tool calling uses the OpenAI function-calling format. Text-protocol
    fallback for models without native tool calls is the agent loop's job,
    not the transport's. Incoming messages are provider-neutral (flat
    `tool_calls` with dict arguments); `_wire_messages` projects them onto
    the OpenAI schema (assistant `tool_calls` with JSON-string arguments,
    `tool_call_id` on tool messages) so strict endpoints accept turn 2+.
    """

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def _base_url(self) -> str:
        return (self._config.base_url or self.DEFAULT_BASE_URL).rstrip("/")

    def _endpoint(self) -> str:
        return f"{self._base_url()}/chat/completions"

    def _headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    @staticmethod
    def _wire_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Project neutral messages onto the OpenAI chat-completions schema."""
        wire: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role", "")
            if role == "assistant" and message.get("tool_calls"):
                wire.append(
                    {
                        "role": "assistant",
                        "content": str(message.get("content") or ""),
                        "tool_calls": [
                            {
                                "id": call.get("id", ""),
                                "type": "function",
                                "function": {
                                    "name": call.get("name", ""),
                                    "arguments": json.dumps(call.get("arguments") or {}),
                                },
                            }
                            for call in message["tool_calls"]
                        ],
                    }
                )
            elif role == "tool":
                wire.append(
                    {
                        "role": "tool",
                        "content": str(message.get("content") or ""),
                        "tool_call_id": str(message.get("tool_call_id") or ""),
                    }
                )
            else:
                wire.append({"role": role, "content": str(message.get("content") or "")})
        return wire

    def _payload(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._config.name,
            "messages": self._wire_messages(messages),
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": tool} for tool in tools]
        return payload

    def _parse_response(
        self, data: dict[str, Any], messages: list[dict[str, Any]]
    ) -> ModelResponse:
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls = [
            ToolCall(
                id=call.get("id", ""),
                name=call.get("function", {}).get("name", ""),
                arguments=_safe_json(call.get("function", {}).get("arguments", "{}")),
            )
            for call in message.get("tool_calls") or []
        ]
        usage = data.get("usage") or {}
        content = message.get("content") or ""
        prompt_estimate = sum(_approx_tokens(str(m.get("content") or "")) for m in messages)
        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            prompt_tokens=int(usage.get("prompt_tokens") or prompt_estimate),
            completion_tokens=int(usage.get("completion_tokens") or _approx_tokens(content)),
            model=data.get("model", self._config.name),
            stop_reason=choice.get("finish_reason", ""),
            provider=self._config.provider,
        )


class OpenAIProvider(OpenAICompatibleProvider):
    """Explicit alias for the official OpenAI endpoint (config clarity)."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
