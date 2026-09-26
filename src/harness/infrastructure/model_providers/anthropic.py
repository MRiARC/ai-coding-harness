"""Anthropic provider (Messages API)."""

from __future__ import annotations

from typing import Any

from harness.infrastructure.model_providers.base import (
    ModelProvider,
    ModelResponse,
    ToolCall,
    _approx_tokens,
)

DEFAULT_BASE_URL = "https://api.anthropic.com"


def _to_anthropic_messages(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Translate OpenAI-style messages into (system, anthropic messages)."""
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []
    for message in messages:
        role, content = message.get("role", ""), message.get("content") or ""
        if role == "system":
            system_parts.append(str(content))
        elif role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message.get("tool_call_id", ""),
                            "content": str(content),
                        }
                    ],
                }
            )
        elif role == "assistant" and message.get("tool_calls"):
            blocks: list[dict[str, Any]] = []
            if content:
                blocks.append({"type": "text", "text": str(content)})
            blocks.extend(
                {
                    "type": "tool_use",
                    "id": call.get("id", ""),
                    "name": call.get("name", ""),
                    "input": call.get("arguments", {}),
                }
                for call in message["tool_calls"]
            )
            out.append({"role": "assistant", "content": blocks})
        else:
            out.append({"role": role, "content": str(content)})
    return "\n\n".join(system_parts), out


class AnthropicProvider(ModelProvider):
    """Claude family via the Messages API; tools use input_schema blocks."""

    def _base_url(self) -> str:
        return (self._config.base_url or DEFAULT_BASE_URL).rstrip("/")

    def _endpoint(self) -> str:
        return f"{self._base_url()}/v1/messages"

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _payload(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> dict[str, Any]:
        system, anthropic_messages = _to_anthropic_messages(messages)
        payload: dict[str, Any] = {
            "model": self._config.name,
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
            "messages": anthropic_messages,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [
                {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("parameters", {"type": "object"}),
                }
                for tool in tools
            ]
        return payload

    def _parse_response(
        self, data: dict[str, Any], messages: list[dict[str, Any]]
    ) -> ModelResponse:
        content_blocks = data.get("content") or []
        text = " ".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        ).strip()
        tool_calls = [
            ToolCall(
                id=block.get("id", ""),
                name=block.get("name", ""),
                arguments=block.get("input") or {},
            )
            for block in content_blocks
            if block.get("type") == "tool_use"
        ]
        usage = data.get("usage") or {}
        prompt_estimate = sum(_approx_tokens(str(m.get("content") or "")) for m in messages)
        return ModelResponse(
            content=text,
            tool_calls=tool_calls,
            prompt_tokens=int(usage.get("input_tokens") or prompt_estimate),
            completion_tokens=int(usage.get("output_tokens") or _approx_tokens(text)),
            model=data.get("model", self._config.name),
            stop_reason=data.get("stop_reason", ""),
            provider=self._config.provider,
        )
