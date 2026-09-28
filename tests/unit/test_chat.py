"""M5+ chat mode: free-spirited interaction (harness chat).

One agent, all tools, persistent session across turns, bare replies are
answers (no TASK_COMPLETE ceremony), scope is the configurable cage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.agents.task import Task
from harness.chat import build_chat_agent, chat_loop, reset_session
from harness.config import HarnessConfig, ModelConfig
from harness.infrastructure.context_store import MemoryContextStore
from harness.infrastructure.model_providers.base import ModelResponse, ToolCall
from harness.infrastructure.model_providers.fake import FakeProvider
from harness.tools.filesystem import WriteFileTool


@pytest.fixture
def chat_config() -> HarnessConfig:
    return HarnessConfig.model_validate(
        {
            "models": {
                "default": {"provider": "fake", "name": "fake", "api_key_env": "AI_API_KEY"}
            },
            "agents": [],
        }
    )


def _lines(*lines: str):
    it = iter(lines)

    def read(prompt: str = "") -> str:
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None

    return read


def _capture():
    out: list[str] = []

    def write(s: str) -> None:
        out.append(s)

    return out, write


def test_chat_bare_reply_ends_turn_and_persists_context(chat_config) -> None:
    """Free-spirited core: no TASK_COMPLETE ceremony; context carries across turns."""
    store = MemoryContextStore()
    config = ModelConfig(provider="fake", name="fake", api_key_env="AI_API_KEY")
    provider = FakeProvider(
        config,
        responses=[
            ModelResponse(content="Hi! I'm Foreman. What shall we build?"),
            ModelResponse(content="A todo app needs three parts: model, storage, UI."),
            ModelResponse(content="Great question — ask me anything else."),
        ],
    )
    agent, _ = build_chat_agent(chat_config, Path("."), store)
    agent.provider = provider

    out, write = _capture()
    chat_loop(
        chat_config,
        Path("."),
        store,
        read=_lines("hello!", "how would we build a todo app?", "nice", "/exit"),
        write=write,
        agent=agent,
    )

    turns = [c for c in provider.calls]
    assert len(turns) == 3
    # turn 2 must contain turn 1's exchange — session memory persists
    second_messages = str(turns[1]["messages"])
    assert "What shall we build" in second_messages
    assert "how would we build a todo app" in second_messages
    # no TASK_COMPLETE ceremony in the chat system prompt
    assert "TASK_COMPLETE" not in turns[0]["messages"][0]["content"]
    joined = "\n".join(out)
    assert "Foreman chat" in joined and "[session] tokens used:" in joined


def test_chat_uses_tools_in_scope(tmp_path: Path, chat_config) -> None:
    """'make a file' just works: the agent writes it inside the scope."""
    store = MemoryContextStore()
    config = ModelConfig(provider="fake", name="fake", api_key_env="AI_API_KEY")
    provider = FakeProvider(
        config,
        responses=[
            ModelResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="w1",
                        name="filesystem_write",
                        arguments={"path": "notes/hello.txt", "content": "hi from chat\n"},
                    )
                ],
            ),
            ModelResponse(content="Done — created notes/hello.txt."),
        ],
    )
    agent, _ = build_chat_agent(chat_config, tmp_path, store)
    agent.provider = provider
    agent.tools = [WriteFileTool(tmp_path)]

    out, write = _capture()
    chat_loop(
        chat_config,
        tmp_path,
        store,
        read=_lines("make a file notes/hello.txt saying hi", "/exit"),
        write=write,
        agent=agent,
    )

    assert (tmp_path / "notes" / "hello.txt").read_text() == "hi from chat\n"
    assert any("Done — created" in line for line in out)


def test_chat_scope_is_the_cage(tmp_path: Path, chat_config) -> None:
    """Writes outside --scope are refused by the tool layer."""
    store = MemoryContextStore()
    config = ModelConfig(provider="fake", name="fake", api_key_env="AI_API_KEY")
    provider = FakeProvider(
        config,
        responses=[
            ModelResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="w1",
                        name="filesystem_write",
                        arguments={"path": "../escape.txt", "content": "nope"},
                    )
                ],
            ),
            ModelResponse(content="TASK_COMPLETE: tried"),
        ],
    )
    agent, _ = build_chat_agent(chat_config, tmp_path, store)
    agent.provider = provider
    agent.tools = [WriteFileTool(tmp_path)]

    import asyncio

    result = asyncio.run(
        agent.execute_task(Task(id="chat-session", title="escape", description="write outside"))
    )
    window = store.load_agent_context("foreman-chat", "chat-session").recent
    tool_turn = next(t for t in window if t.role == "tool")
    assert "escapes the repository root" in tool_turn.content
    del result


def test_chat_new_resets_session(chat_config) -> None:
    """/new wipes the conversation window; the agent starts fresh."""
    store = MemoryContextStore()
    config = ModelConfig(provider="fake", name="fake", api_key_env="AI_API_KEY")
    provider = FakeProvider(
        config,
        responses=[
            ModelResponse(content="first answer"),
            ModelResponse(content="fresh start — what context?"),
        ],
    )
    agent, _ = build_chat_agent(chat_config, Path("."), store)
    agent.provider = provider

    out, write = _capture()
    chat_loop(
        chat_config,
        Path("."),
        store,
        read=_lines("remember this: xylophone", "/new", "what did I say?", "/exit"),
        write=write,
        agent=agent,
    )

    # after /new the second turn's window must NOT contain the first exchange
    second_messages = str(provider.calls[1]["messages"])
    assert "xylophone" not in second_messages
    assert any("[new session]" in line for line in out)


def test_reset_session_clears_store(chat_config) -> None:
    store = MemoryContextStore()
    store.append_turn("foreman-chat", "chat-session", "user", "old stuff")
    reset_session(store)
    ctx = store.load_agent_context("foreman-chat", "chat-session")
    assert ctx.recent == [] and ctx.summary == ""


def test_chat_unknown_role_rejected(chat_config) -> None:
    from harness.agents.specialists import build_agent

    with pytest.raises(ValueError, match="unknown role"):
        build_agent(
            agent_id="x", role="nope", model_config={}, provider=None, store=None, governor=None
        )


def test_chat_turn_step_limit_hint(chat_config) -> None:
    """A step-limited turn surfaces the continuation hint (max_steps=1)."""
    store = MemoryContextStore()
    config = ModelConfig(provider="fake", name="fake", api_key_env="AI_API_KEY")
    provider = FakeProvider(
        config,
        responses=[
            ModelResponse(
                content="",
                tool_calls=[ToolCall(id="n1", name="noop", arguments={})],
            )
        ],
    )
    agent, _ = build_chat_agent(chat_config, Path("."), store, max_steps=1)
    agent.provider = provider

    out, write = _capture()
    chat_loop(
        chat_config,
        Path("."),
        store,
        max_steps=1,
        read=_lines("do something long", "/exit"),
        write=write,
        agent=agent,
    )
    assert any("step limit" in line for line in out)


def test_chat_cli_command_wires_scope_and_store(tmp_path: Path, monkeypatch) -> None:
    """`harness chat` builds the session from --scope and persists to sqlite."""

    from harness import cli

    scope = tmp_path / "workspace"
    scope.mkdir()
    monkeypatch.chdir(tmp_path)
    import builtins

    inputs = iter(["/exit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(inputs))

    scope_value = str(scope)

    class Args:
        scope = scope_value
        max_steps = None

    code = cli.chat_command(Args)
    assert code == 0
    from harness.state import state_root

    assert (state_root(scope) / "chat.db").exists()  # broad scope → ~/.foreman/<hash>


def test_chat_eof_and_blank_and_exit_variants(chat_config) -> None:
    """EOF breaks cleanly; blank lines are skipped; bare 'quit' also exits."""
    store = MemoryContextStore()
    config = ModelConfig(provider="fake", name="fake", api_key_env="AI_API_KEY")
    provider = FakeProvider(
        config,
        responses=[ModelResponse(content="answer one"), ModelResponse(content="answer two")],
    )
    agent, _ = build_chat_agent(chat_config, Path("."), store)
    agent.provider = provider

    out, write = _capture()
    chat_loop(
        chat_config,
        Path("."),
        store,
        read=_lines("", "quit"),
        write=write,
        agent=agent,
    )
    assert any("[session] tokens used:" in line for line in out)


def test_chat_command_missing_scope(tmp_path: Path, monkeypatch) -> None:
    from harness import cli

    monkeypatch.chdir(tmp_path)

    class Args:
        scope = str(tmp_path / "does-not-exist")
        max_steps = None

    assert cli.chat_command(Args) == 2


def test_chat_dispatch_via_main(monkeypatch, tmp_path: Path) -> None:
    """`harness chat` dispatches through main with the --scope flag."""
    import builtins

    from harness import cli

    scope = tmp_path / "ws"
    scope.mkdir()
    monkeypatch.chdir(tmp_path)
    inputs = iter(["/exit"])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(inputs))

    assert cli.main(["chat", "--scope", str(scope)]) == 0
    from harness.state import state_root

    assert (state_root(scope) / "chat.db").exists()  # broad scope → ~/.foreman/<hash>


def test_chat_immediate_eof_exits_cleanly(chat_config) -> None:
    """An exhausted input stream (EOF) exits the session with code 0."""
    store = MemoryContextStore()
    agent, _ = build_chat_agent(chat_config, Path("."), store)

    out, write = _capture()
    code = chat_loop(
        chat_config,
        Path("."),
        store,
        read=_lines(),
        write=write,
        agent=agent,
    )
    assert code == 0
    assert any("tokens used" in line for line in out)


def test_chat_auth_error_is_friendly_not_fatal(chat_config, monkeypatch) -> None:
    """Without a key: a clear hint, no traceback, graceful exit."""
    from harness.infrastructure.model_providers.base import ModelAuthError

    store = MemoryContextStore()

    class AuthFailProvider(FakeProvider):
        async def generate(self, *args, **kwargs):
            raise ModelAuthError("environment variable 'AI_API_KEY' is not set")

    agent, _ = build_chat_agent(chat_config, Path("."), store)
    agent.provider = AuthFailProvider(chat_config.models["default"], responses=[])

    out, write = _capture()
    code = chat_loop(
        chat_config,
        Path("."),
        store,
        read=_lines("hello", "/exit"),
        write=write,
        agent=agent,
    )
    joined = "\n".join(out)
    assert "[error] environment variable" in joined
    assert "export AI_API_KEY" in joined
    assert code == 0


def test_chat_transient_error_keeps_session(chat_config) -> None:
    """A gateway failure prints a hint and the session continues intact."""
    store = MemoryContextStore()

    class FlakyProvider(FakeProvider):
        def __init__(self, cfg):
            super().__init__(cfg, responses=[ModelResponse(content="recovered")])
            self.failed_once = False

        async def generate(self, *args, **kwargs):
            if not self.failed_once:
                self.failed_once = True
                raise RuntimeError("gateway connection refused")
            return await super().generate(*args, **kwargs)

    agent, _ = build_chat_agent(chat_config, Path("."), store)
    agent.provider = FlakyProvider(chat_config.models["default"])  # same ModelConfig

    out, write = _capture()
    chat_loop(
        chat_config,
        Path("."),
        store,
        read=_lines("do the thing", "and again", "/exit"),
        write=write,
        agent=agent,
    )
    joined = "\n".join(out)
    assert "model call failed" in joined and "gateway connection refused" in joined
    assert "foreman> recovered" in joined  # the session continued after the failure


def test_chat_meter_is_per_session(chat_config) -> None:
    """Two sessions from the same scope report their OWN spend."""
    store = MemoryContextStore()

    agent1, _ = build_chat_agent(chat_config, Path("."), store)
    agent1.governor.record("foreman-chat", "fake", 1000, 0)
    assert agent1.governor.used_tokens() == 1000

    agent2, _ = build_chat_agent(chat_config, Path("."), store)
    assert agent2.governor.used_tokens() == 0  # fresh correlation id
    assert agent1.governor.correlation_id != agent2.governor.correlation_id


def test_chat_shell_passthrough_and_interrupt(chat_config) -> None:
    """!command runs locally without the model; KI mid-turn cancels cleanly."""
    store = MemoryContextStore()
    agent, _ = build_chat_agent(chat_config, Path("."), store)

    class ExplodingProvider(FakeProvider):
        async def generate(self, *args, **kwargs):
            raise KeyboardInterrupt()

    agent.provider = ExplodingProvider(chat_config.models["default"], responses=[])

    out, write = _capture()
    chat_loop(
        chat_config,
        Path("."),
        store,
        read=_lines("!echo passthrough-works", "hi", "/exit"),
        write=write,
        agent=agent,
    )
    joined = "\n".join(out)
    assert "passthrough-works" in joined  # ! ran locally
    assert "[interrupted] turn cancelled" in joined  # KI mid-turn cancelled
    assert len(agent.provider.calls) == 0  # the KI turn never reached the model
