"""Free-form chat mode (`harness chat`): talk to Foreman like a colleague.

One agent, all tools, one persistent session: context carries across turns,
the workspace scope is whatever you point `--scope` at (default: cwd), and
simple asks get direct action — no architect/manager ceremony. Token
metering still applies to every call; the cage is the `--scope` you choose.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from harness.agents.llm_agent import LLMAgent
from harness.agents.task import Task
from harness.config import HarnessConfig
from harness.engine.budget import BudgetGovernor
from harness.infrastructure.context_store import ContextStore
from harness.infrastructure.model_providers import create_model_provider
from harness.infrastructure.model_providers.base import ModelAuthError
from harness.tools.registry import build_default_tools

CHAT_TASK = "chat-session"
CHAT_AGENT_ID = "foreman-chat"


def build_chat_agent(
    config: HarnessConfig,
    scope: Path,
    store: ContextStore,
    max_steps: int | None = None,
    correlation_id: str | None = None,
) -> tuple[LLMAgent, Any]:
    """The chat agent: one generalist, every tool, scoped to `scope`.

    Each session gets its own correlation id so the token meter reports
    THIS session's spend, not every chat ever run from the scope.
    """
    import time

    from harness.agents.specialists import build_agent

    model_cfg = config.models["default"]
    provider = create_model_provider(model_cfg)
    governor = BudgetGovernor(store, config.budget, correlation_id or f"chat-{time.time_ns()}")
    tools = build_default_tools(scope)
    steps = max_steps if max_steps is not None else config.run.max_steps
    agent = build_agent(
        agent_id=CHAT_AGENT_ID,
        role="chat",
        model_config={"provider": model_cfg.provider},
        provider=provider,
        store=store,
        governor=governor,
        tools=tools,
        task_id=CHAT_TASK,
        max_steps=steps,
        require_marker=False,  # a bare reply IS the answer in chat
        persistent_window=True,  # session memory across turns
    )
    return agent, provider


def reset_session(store: ContextStore) -> None:
    """Wipe the chat window (same backend, fresh context)."""
    from harness.infrastructure.context_store import AgentContext

    store.save_agent_context(AgentContext(agent_id=CHAT_AGENT_ID, task_id=CHAT_TASK))


def chat_loop(
    config: HarnessConfig,
    scope: Path,
    store: ContextStore,
    max_steps: int | None = None,
    read: Any = None,
    write: Any = None,
    agent: LLMAgent | None = None,
) -> int:
    """Interactive REPL. `read`/`write`/`agent` are injectable for tests."""
    read = read or input
    write = write or (lambda s: print(s, flush=True))
    if agent is None:
        agent, _provider = build_chat_agent(config, scope, store, max_steps)

    write("Foreman chat — plain language, real tools. /new resets context, /exit quits.")
    write(f"scope: {scope}")
    while True:
        try:
            line = read("you> ")
        except (EOFError, KeyboardInterrupt):
            break
        line = line.strip()
        if not line:
            continue
        if line in {"/exit", "/quit", "exit", "quit"}:
            break
        if line == "/new":
            reset_session(store)
            write("[new session] context cleared; same tools, same scope.")
            continue
        task = Task(id=CHAT_TASK, title=line[:80], description=line)
        try:
            result = asyncio.run(agent.execute_task(task))
        except ModelAuthError as exc:
            write(f"[error] {exc}")
            write("[hint] export AI_API_KEY=<your key> and start the session again.")
            break
        except Exception as exc:
            # the session context is intact; a retry usually just works
            write(f"[error] model call failed: {str(exc)[:300]}")
            write("[hint] your context is intact — try the request again.")
            continue
        write(f"foreman> {result.summary or result.error or '(no output)'}")
        if result.error and "step limit" in result.error:
            write("[hint] step limit hit — ask me to continue, or raise run.max_steps.")
    write(f"[session] tokens used: {agent.governor.used_tokens()}")
    return 0
