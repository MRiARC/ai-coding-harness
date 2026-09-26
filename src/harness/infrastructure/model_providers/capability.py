"""Model capability probe (M5 hardening; improvements §3.1).

Never assume the model's calling convention: probe it once, cache the
result, and let the agent loop pick native tool calling or the text
protocol accordingly. The prescribed model is unknown until evaluation
time — models that lack native function calling (or proxies that mangle
tool_calls) must not paralyze the harness.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from harness.infrastructure.logging import get_logger
from harness.infrastructure.model_providers.base import ModelProvider

logger = get_logger(__name__)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)

_PROBE_TOOLS = [
    {
        "name": "list_files",
        "description": "List files in a directory",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }
]
_PROBE_PROMPT = "List the files in the current directory using the list_files tool."


@dataclass(frozen=True)
class ModelCapabilities:
    """Observed calling conventions for one model."""

    native_tool_calls: bool
    json_reply_ok: bool | None = None
    thinks: bool = False
    probed_at: float = 0.0
    detail: str = ""


def strip_think_blocks(text: str) -> str:
    """Remove `<think>…</think>` reasoning blocks (Qwen-style) from content."""
    if "<think>" not in text:
        return text
    return _THINK_RE.sub("", text).strip()


async def probe_capabilities(provider: ModelProvider) -> ModelCapabilities:
    """One cheap round-trip: does the model emit native `tool_calls`?"""
    try:
        response = await provider.generate(
            [{"role": "user", "content": _PROBE_PROMPT}],
            tools=_PROBE_TOOLS,
        )
        native = bool(response.tool_calls)
        raw = response.content or ""
        thinks = "<think>" in raw
        detail = f"finish={response.stop_reason or '?'} tool_calls={len(response.tool_calls)}"
    except Exception as exc:
        logger.warning("capability probe failed; assuming native tool calls", error=str(exc)[:200])
        return ModelCapabilities(
            native_tool_calls=True, probed_at=time.time(), detail=f"probe failed: {str(exc)[:120]}"
        )
    return ModelCapabilities(
        native_tool_calls=native,
        thinks=thinks,
        probed_at=time.time(),
        detail=detail,
    )


class CapabilityCache:
    """One probe per model per process (keyed like the config names them)."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str, str], ModelCapabilities] = {}

    @staticmethod
    def key(provider: ModelProvider) -> tuple[str, str, str]:
        cfg = provider._config
        return (cfg.provider, cfg.name, cfg.base_url or "")

    def get(self, provider: ModelProvider) -> ModelCapabilities | None:
        return self._cache.get(self.key(provider))

    def put(self, provider: ModelProvider, caps: ModelCapabilities) -> ModelCapabilities:
        self._cache[self.key(provider)] = caps
        return caps

    async def get_or_probe(self, provider: ModelProvider) -> ModelCapabilities:
        cached = self.get(provider)
        if cached is not None:
            return cached
        scripted = getattr(provider, "capabilities", None)  # FakeProvider seam
        if scripted is not None:
            return self.put(provider, scripted)
        return self.put(provider, await probe_capabilities(provider))


def render_tool_manual(tools: list[dict[str, Any]]) -> str:
    """Render tool schemas as text instructions for the text protocol."""
    if not tools:
        return ""
    lines = [
        "AVAILABLE TOOLS (call them with the text protocol below):",
    ]
    for tool in tools:
        args = json.dumps(tool.get("parameters", {"type": "object"}))
        lines.append(f"- {tool['name']}: {tool.get('description', '')} | args schema: {args}")
    lines.append(
        "\nTO CALL A TOOL, reply with one line per call in exactly this format:\n"
        'TOOL_CALL: {"name": "<tool name>", "arguments": {<json arguments>}}\n'
        "You will receive each result as a TOOL_RESULT message. "
        "When the task is done, reply with 'TASK_COMPLETE: <summary>' and no TOOL_CALL lines."
    )
    return "\n".join(lines)


def parse_tool_call_blocks(text: str) -> list[dict[str, Any]]:
    """Extract `TOOL_CALL: {...}` directives from a plain-text reply.

    Tolerant of code fences and prose around the directives; malformed JSON
    lines are surfaced as arguments errors by the normal tool path.
    """
    calls: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.upper().startswith("TOOL_CALL:"):
            continue
        raw = stripped.split(":", 1)[1].strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            calls.append({"id": "", "name": "", "arguments": {"_unparsed": raw[:200]}})
            continue
        if isinstance(parsed, dict):
            calls.append(
                {
                    "id": str(parsed.get("id", "")),
                    "name": str(parsed.get("name", "")),
                    "arguments": parsed.get("arguments") or {},
                }
            )
    return calls
