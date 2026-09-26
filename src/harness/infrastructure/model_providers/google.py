"""Google provider (Gemini generateContent API)."""

from __future__ import annotations

from typing import Any

from harness.infrastructure.model_providers.base import (
    ModelProvider,
    ModelResponse,
    ToolCall,
    _approx_tokens,
)

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"


def _to_gemini_contents(
    messages: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Translate OpenAI-style messages into (systemInstruction, contents)."""
    system_parts: list[str] = []
    contents: list[dict[str, Any]] = []
    for message in messages:
        role, content = message.get("role", ""), message.get("content") or ""
        if role == "system":
            system_parts.append(str(content))
            continue
        gemini_role = "model" if role == "assistant" else "user"
        parts: list[dict[str, Any]] = []
        if role == "tool":
            parts.append(
                {
                    "functionResponse": {
                        "name": message.get("name", "tool"),
                        "response": {"result": str(content)},
                    }
                }
            )
            gemini_role = "user"
        elif role == "assistant" and message.get("tool_calls"):
            if content:
                parts.append({"text": str(content)})
            parts.extend(
                {"functionCall": {"name": call.get("name", ""), "args": call.get("arguments", {})}}
                for call in message["tool_calls"]
            )
        elif content:
            parts.append({"text": str(content)})
        if parts:
            contents.append({"role": gemini_role, "parts": parts})
    system_instruction = {"parts": [{"text": "\n\n".join(system_parts)}]} if system_parts else None
    return system_instruction, contents


class GoogleProvider(ModelProvider):
    """Gemini family via generateContent; tools use functionDeclarations."""

    def _base_url(self) -> str:
        return (self._config.base_url or DEFAULT_BASE_URL).rstrip("/")

    def _endpoint(self) -> str:
        return f"{self._base_url()}/v1beta/models/{self._config.name}:generateContent"

    def _headers(self, api_key: str) -> dict[str, str]:
        return {"x-goog-api-key": api_key, "Content-Type": "application/json"}

    def _payload(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> dict[str, Any]:
        system_instruction, contents = _to_gemini_contents(messages)
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self._config.temperature,
                "maxOutputTokens": self._config.max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": tool["name"],
                            "description": tool.get("description", ""),
                            "parameters": tool.get("parameters", {"type": "object"}),
                        }
                        for tool in tools
                    ]
                }
            ]
        return payload

    def _parse_response(
        self, data: dict[str, Any], messages: list[dict[str, Any]]
    ) -> ModelResponse:
        candidate = (data.get("candidates") or [{}])[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        text = " ".join(part.get("text", "") for part in parts if "text" in part).strip()
        tool_calls = [
            ToolCall(
                name=part.get("functionCall", {}).get("name", ""),
                arguments=part.get("functionCall", {}).get("args") or {},
            )
            for part in parts
            if "functionCall" in part
        ]
        usage = data.get("usageMetadata") or {}
        prompt_estimate = sum(_approx_tokens(str(m.get("content") or "")) for m in messages)
        return ModelResponse(
            content=text,
            tool_calls=tool_calls,
            prompt_tokens=int(usage.get("promptTokenCount") or prompt_estimate),
            completion_tokens=int(usage.get("candidatesTokenCount") or _approx_tokens(text)),
            model=self._config.name,
            stop_reason=candidate.get("finishReason", ""),
            provider=self._config.provider,
        )
