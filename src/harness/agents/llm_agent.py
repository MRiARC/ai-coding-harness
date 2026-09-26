"""Concrete LLM-backed agent loop (milestone 2, issue 2.7 - specialist base).

`LLMAgent` implements the `BaseAgent` contract over a model provider and the
context store:

- every step checks the budget governor and records usage to the ledger;
- tool calls go through validation + permission gating, and failures become
  tool results (never exceptions) so the recovery ladder can reason over them;
- the conversation lives in the store's three-window context, compressed
  automatically when the recent window grows past `keep_recent`;
- bare replies end the loop (optionally marked with `TASK_COMPLETE:`), and a
  structured-JSON helper with one repair round supports the Architect/Manager
  contracts.
"""

from __future__ import annotations

import json
from typing import Any

from harness.agents.base import BaseAgent, ContextWindow
from harness.agents.prompts import FINAL_MARKER, ROLE_PRESETS, RolePreset, system_prompt
from harness.agents.task import Task, TaskResult
from harness.engine.budget import BudgetExhausted, BudgetGovernor
from harness.infrastructure.context_store import ContextStore
from harness.infrastructure.logging import get_logger
from harness.infrastructure.model_providers import (
    ModelProvider,
    ModelResponse,
)
from harness.orchestration.messages import AgentStatus, ErrorEscalation, Severity, StatusUpdate
from harness.tools.base import AsyncExecutableTool, Tool, ToolResult, ToolTier

logger = get_logger(__name__)

DEFAULT_KEEP_RECENT = 24
DEFAULT_MAX_STEPS = 16

_STEP_LIMIT_ERROR = "step limit reached before the agent finished"


class StructuredOutputError(Exception):
    """The model's reply could not be parsed as the required JSON structure."""


def compose_task_prompt(task: Task) -> str:
    """Full task brief for a specialist (audit §9).

    Planning output must reach execution: the description is joined by the
    Architect's acceptance criteria, the expected files, the required tools,
    and any Manager guidance attached to the task. Long sections are capped
    (observation compression, improvements §2.2).
    """
    sections = [f"TASK: {task.title}", task.description.strip()]
    if task.acceptance_criteria:
        criteria = "\n".join(f"- {c[:200]}" for c in task.acceptance_criteria[:10])
        sections.append(f"ACCEPTANCE CRITERIA:\n{criteria}")
    if task.files:
        sections.append("EXPECTED FILES: " + ", ".join(task.files[:12]))
    if task.required_tools:
        sections.append("REQUIRED TOOLS: " + ", ".join(task.required_tools[:12]))
    guidance = task.metadata.get("guidance")
    if guidance:
        sections.append(f"MANAGER GUIDANCE: {str(guidance)[:600]}")
    return "\n\n".join(sections)


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model reply.

    Accepts bare JSON, ```json fenced blocks, or JSON embedded in prose.
    Raises `StructuredOutputError` when no object is present.
    """
    fenced_start = text.find("```json")
    if fenced_start >= 0:
        candidate = text[fenced_start + 7 :]
        fenced_end = candidate.find("```")
        if fenced_end >= 0:
            candidate = candidate[:fenced_end]
    else:
        brace_start = text.find("{")
        if brace_start < 0:
            msg = f"no JSON object found in reply: {text[:120]!r}"
            raise StructuredOutputError(msg)
        candidate = _balanced_object(text, brace_start)
    if not candidate.strip():
        msg = f"no JSON object found in reply: {text[:120]!r}"
        raise StructuredOutputError(msg)
    try:
        parsed = json.loads(candidate.strip())
    except json.JSONDecodeError as exc:
        msg = f"invalid JSON in model reply: {exc}"
        raise StructuredOutputError(msg) from exc
    if not isinstance(parsed, dict):
        msg = f"expected a JSON object, got {type(parsed).__name__}"
        raise StructuredOutputError(msg)
    return parsed


def _balanced_object(text: str, start: int) -> str:
    """Slice the first balanced {...} object starting at `start` (quote-aware)."""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    msg = "unterminated JSON object in reply"
    raise StructuredOutputError(msg)


class StoreWindow:
    """ContextWindow implementation backed by the context store."""

    def __init__(self, store: ContextStore, agent_id: str, task_id: str) -> None:
        self._store = store
        self._agent_id = agent_id
        self._task_id = task_id

    def append(
        self,
        role: str,
        content: str,
        *,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str = "",
        tool_name: str = "",
    ) -> None:
        self._store.append_turn(
            self._agent_id,
            self._task_id,
            role,
            content,
            tool_calls=tool_calls,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )

    def as_messages(self) -> list[dict[str, Any]]:
        """Provider-neutral projection of the recent window.

        Assistant turns carrying `tool_calls` emit them flat
        (`{id, name, arguments}`); tool turns emit their `tool_call_id` and
        `tool_name`. Each provider projects this onto its own wire format in
        its `_payload`, so the native tool-calling protocol round-trips.
        """
        context = self._store.load_agent_context(self._agent_id, self._task_id)
        messages: list[dict[str, Any]] = []
        for turn in context.recent:
            message: dict[str, Any] = {"role": turn.role, "content": turn.content}
            if turn.tool_calls:
                message["tool_calls"] = [
                    {
                        "id": call.get("id", ""),
                        "name": call.get("name", ""),
                        "arguments": call.get("arguments") or {},
                    }
                    for call in turn.tool_calls
                ]
            if turn.tool_call_id:
                message["tool_call_id"] = turn.tool_call_id
                message["tool_name"] = turn.tool_name
            messages.append(message)
        return messages


class LLMAgent(BaseAgent):
    """Agent loop over a model provider with tools, budgeting, and context."""

    def __init__(
        self,
        agent_id: str,
        model_config: dict[str, Any],
        tools: list[Tool],
        context_window: ContextWindow,
        provider: ModelProvider,
        store: ContextStore,
        governor: BudgetGovernor,
        role: str = "implementer",
        model_tier: int = 3,
        max_steps: int = DEFAULT_MAX_STEPS,
        keep_recent: int = DEFAULT_KEEP_RECENT,
    ) -> None:
        super().__init__(agent_id, model_config, tools, context_window)
        self.provider = provider
        self.store = store
        # The pipeline replaces this placeholder with the per-run governor
        # before execute_task; constructing without one is a wiring error.
        self.governor = governor
        self.role = role
        self.model_tier = model_tier
        self.max_steps = max_steps
        self.keep_recent = keep_recent
        self._active_task: str | None = None
        self._attempts: dict[str, int] = {}

    # -- BaseAgent contract ---------------------------------------------------
    @property
    def preset(self) -> RolePreset | None:
        return ROLE_PRESETS.get(self.role)

    async def execute_task(self, task: Task) -> TaskResult:
        """Run the tool loop until the model stops calling tools or limits hit."""
        self._active_task = task.id
        # Rebind the window to *this* task: agents are reusable, and a stale
        # window would split the conversation across task ids or hide the
        # task text from the first model call (audit §10).
        self.context_window = StoreWindow(self.store, self.agent_id, task.id)
        self.context_window.append("user", compose_task_prompt(task))
        try:
            summary, success, error = await self._loop(task)
        except BudgetExhausted:
            self._record_milestone(task, success=False, note="stopped: token budget")
            return self.governor.exhausted_result(task.id)
        finally:
            self._active_task = None
        if success:
            self._record_milestone(task, success=True, note=summary[:200])
        return TaskResult(task_id=task.id, success=success, summary=summary, error=error)

    async def structured_call(
        self, instruction: str, user_prompt: str, schema_hint: str
    ) -> dict[str, Any]:
        """One JSON-structured model call with a single repair round.

        The Architect/Manager contracts need parsed structures, not prose:
        first ask, and on a malformed reply ask once more with the schema
        restated before giving up (feeds the recovery ladder as evidence).
        """
        self.context_window.append("user", user_prompt)
        reply = await self._generate(instruction)
        try:
            return extract_json(reply.content)
        except StructuredOutputError:
            repair = (
                f"Your last reply was not valid JSON for the required schema.\n"
                f"Schema: {schema_hint}\nReply with ONLY the JSON object."
            )
            self.context_window.append("user", repair)
            reply = await self._generate(instruction)
            parsed = extract_json(reply.content)
            self.context_window.append("assistant", "recovered with valid JSON")
            return parsed

    async def _generate(self, instruction: str) -> ModelResponse:
        self.governor.check()
        response = await self.provider.generate(
            [
                {"role": "system", "content": system_prompt(self.role, extra=instruction)},
                *self.context_window.as_messages(),
            ],
            self._tool_schemas(),
        )
        self.governor.record(
            self.agent_id, self.provider.model, response.prompt_tokens, response.completion_tokens
        )
        self.context_window.append("assistant", response.content or "")
        return response

    async def handle_error(self, error: Exception, task: Task) -> ErrorEscalation:
        """Classify a failure for the recovery ladder (issue 2.11 contract)."""
        self._attempts[task.id] = self._attempts.get(task.id, 0) + 1
        severity = _classify_error(error)
        return ErrorEscalation(
            sender=self.agent_id,
            task_id=task.id,
            severity=severity,
            error_type=type(error).__name__,
            message=str(error)[:500],
            attempt=self._attempts[task.id],
        )

    def report_status(self) -> StatusUpdate:
        status = AgentStatus.WORKING if self._active_task else AgentStatus.IDLE
        return StatusUpdate(sender=self.agent_id, status=status, task_id=self._active_task)

    # -- loop internals ---------------------------------------------------------
    async def _loop(self, task: Task) -> tuple[str, bool, str | None]:
        context = self.store.load_agent_context(self.agent_id, task.id)
        ledger = context.summary if context.summary else ""
        for _step in range(self.max_steps):
            self.governor.check()
            response = await self.provider.generate(
                self._messages(task, ledger), self._tool_schemas()
            )
            self.governor.record(
                self.agent_id,
                self.provider.model,
                response.prompt_tokens,
                response.completion_tokens,
            )
            if response.tool_calls:
                calls: list[dict[str, Any]] = [
                    {
                        "id": call.id or f"call_{index + 1}",
                        "name": call.name,
                        "arguments": call.arguments,
                    }
                    for index, call in enumerate(response.tool_calls)
                ]
                self.context_window.append("assistant", response.content or "", tool_calls=calls)
                for call in calls:
                    result = await self._invoke_tool(call["name"], call["arguments"])
                    self.context_window.append(
                        "tool",
                        f"[{call['name']}] {result.output or result.error}",
                        tool_call_id=call["id"],
                        tool_name=call["name"],
                    )
                continue
            self.context_window.append("assistant", response.content or "")
            self._maybe_compress(task.id)
            return response.content, True, None
        self._maybe_compress(task.id)
        return _STEP_LIMIT_ERROR, False, _STEP_LIMIT_ERROR

    def _messages(self, task: Task, ledger: str) -> list[dict[str, Any]]:
        return [
            {
                "role": "system",
                "content": system_prompt(
                    self.role,
                    fact_ledger=ledger,
                    extra=f"Working repo task id: {task.id}. End with {FINAL_MARKER} when done.",
                ),
            },
            *self.context_window.as_messages(),
        ]

    def _tool_schemas(self) -> list[dict[str, Any]]:
        permitted = self.permitted_tools({"agent_id": self.agent_id, "model_tier": self.model_tier})
        allowed_tier = self.preset.max_tool_tier if self.preset else ToolTier.ADVANCED
        return [
            {"name": tool.name, "description": tool.description, "parameters": tool.parameters}
            for tool in permitted
            if tool.tier <= allowed_tier
        ]

    async def _invoke_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = next((t for t in self.tools if t.name == name), None)
        if tool is None:
            return ToolResult(success=False, error=f"unknown tool '{name}'")
        if errors := tool.validate_input(arguments):
            return ToolResult(success=False, error=f"invalid arguments: {'; '.join(errors)}")
        context = {"agent_id": self.agent_id, "model_tier": self.model_tier}
        if not tool.check_permissions(context):
            return ToolResult(
                success=False,
                error=f"permission denied for tool '{name}' at tier {self.model_tier}",
            )
        result = await _call_tool(tool, arguments)
        self.governor.record(self.agent_id, f"tool:{name}", 0, 0)
        return result

    def _maybe_compress(self, task_id: str) -> None:
        context = self.store.load_agent_context(self.agent_id, task_id)
        if len(context.recent) >= self.keep_recent:
            folded = self.store.compress(self.agent_id, task_id, keep_recent=self.keep_recent // 2)
            if folded:
                logger.info("context compressed", agent=self.agent_id, folded=folded)

    def _record_milestone(self, task: Task, *, success: bool, note: str) -> None:
        context = self.store.load_agent_context(self.agent_id, task.id)
        context.milestones.append(("OK" if success else "FAIL") + f": {note}")
        self.store.save_agent_context(context)


async def _call_tool(tool: Tool, arguments: dict[str, Any]) -> ToolResult:
    try:
        if isinstance(tool, AsyncExecutableTool):
            return await tool.execute_async(**arguments)
        return tool.execute(**arguments)
    except Exception as exc:
        return ToolResult(success=False, error=f"tool crashed: {exc}")


def _classify_error(error: Exception) -> Severity:
    """Error classification per DESIGN_SPEC §7.1."""
    if isinstance(error, BudgetExhausted):
        return Severity.FATAL
    if isinstance(error, (TimeoutError, ConnectionError)):
        return Severity.TRANSIENT
    if isinstance(error, (StructuredOutputError, json.JSONDecodeError, ValueError)):
        return Severity.RECOVERABLE
    return Severity.RECOVERABLE
