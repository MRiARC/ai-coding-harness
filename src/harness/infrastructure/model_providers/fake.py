"""Fake provider: scripted, offline, deterministic (the test-suite backbone).

`make test` runs the whole harness against this provider without any API key
or network access; the live eval swaps in a real provider via configuration.
"""

from __future__ import annotations

from typing import Any

from harness.infrastructure.model_providers.base import (
    ModelProvider,
    ModelResponse,
    _approx_tokens,
)


class FakeProvider(ModelProvider):
    """Replays a scripted sequence of responses.

    Entries may be `ModelResponse`s (replayed verbatim) or `Exception`s
    (raised once, useful for retry/recovery tests). Exhausting the script
    fails loudly rather than hallucinating further responses.
    """

    def __init__(self, config: Any, responses: list[Any]) -> None:
        super().__init__(config)
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def _resolve_api_key(self) -> str:
        return "fake-key"

    def _endpoint(self) -> str:
        return "fake://generate"

    def _headers(self, api_key: str) -> dict[str, str]:
        return {}

    def _payload(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> dict[str, Any]:
        return {"messages": messages, "tools": tools or []}

    def _parse_response(
        self, data: dict[str, Any], messages: list[dict[str, Any]]
    ) -> ModelResponse:  # pragma: no cover - never reached (generate is overridden)
        raise NotImplementedError

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **overrides: Any,
    ) -> ModelResponse:
        self.calls.append({"messages": messages, "tools": tools, "overrides": overrides})
        if not self._responses:
            msg = (
                f"FakeProvider script exhausted after {len(self.calls) - 1} calls; "
                "extend the script in the test"
            )
            raise RuntimeError(msg)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        prompt_estimate = sum(_approx_tokens(str(m.get("content") or "")) for m in messages)
        item.prompt_tokens = item.prompt_tokens or prompt_estimate
        item.completion_tokens = item.completion_tokens or _approx_tokens(item.content)
        return item
