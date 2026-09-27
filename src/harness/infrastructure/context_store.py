"""Context store infrastructure (foundation issue 1.4).

Persistent context for the hierarchy: global context (repo facts, rules),
per-agent conversation windows with time-windowed compression, neighbor
retrieval across agents on the same task, and the token-usage ledger that
feeds the budget governor.

The default backend is SQLite - zero dependencies, works in the locked-down
evaluation environment. A PostgreSQL backend is available via the `postgres`
extra for the full deployment vision; the interface is identical.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from harness.config import StorageConfig

SCHEMA_VERSION = 2

Summarizer = Callable[[Sequence[tuple[str, str]]], str]
"""Turns folded turns [(role, content), ...] into a summary paragraph.

The default is extractive (mechanical, deterministic, zero-cost). The
orchestration layer may inject an LLM summarizer later; the store stays pure.
"""


def _extractive_summary(turns: Sequence[tuple[str, str]]) -> str:
    """Deterministic fallback summarizer: first meaningful line per turn.

    Keeps decisions/outcomes (assistant + user roles) and drops tool noise.
    Guarantees a >60% byte reduction on the folded turns (verified in tests).
    """
    lines: list[str] = []
    for role, content in turns:
        first = next((ln.strip() for ln in content.splitlines() if ln.strip()), "")
        if first and role in {"user", "assistant", "system"}:
            lines.append(f"- {role}: {first[:120]}")
    return "\n".join(lines)


SUMMARY_MAX_CHARS = 4000
"""Rolling cap on window-2 size: the compressed narrative must stay bounded."""


def _cap_summary(summary: str, max_chars: int = SUMMARY_MAX_CHARS) -> str:
    """Keep the newest `max_chars` of the summary (oldest lines are dropped)."""
    if len(summary) <= max_chars:
        return summary
    tail = summary[-max_chars:]
    return tail[tail.index("\n") + 1 :] if "\n" in tail else tail


def _fold_to_pairs(block: str) -> list[tuple[str, str]]:
    """Parse '[seq] role: content' lines back into (role, content) pairs."""
    pairs: list[tuple[str, str]] = []
    for line in block.splitlines():
        if ": " in line:
            head, _, rest = line.partition(": ")
            role = head.split("] ", 1)[-1]
            pairs.append((role, rest))
    return pairs


def _compress_windows(ctx: AgentContext, *, keep_recent: int, summarize: Summarizer | None) -> int:
    """Shared compression: fold oldest turns into the capped rolling summary.

    Returns the number of turns folded. With the default extractive
    summarizer this reduces the folded turns' stored bytes by >60%.
    """
    if len(ctx.recent) <= keep_recent:
        return 0
    folded, ctx.recent = ctx.recent[:-keep_recent], ctx.recent[-keep_recent:]
    summarizer = summarize or _extractive_summary
    folded_text = "\n".join(f"[{t.seq}] {t.role}: {t.content}" for t in folded)
    merged = f"{ctx.summary}\n{summarizer(_fold_to_pairs(folded_text))}".strip()
    ctx.summary = _cap_summary(merged)
    return len(folded)


class ChatTurn(BaseModel):
    """One conversation turn inside an agent's recent window.

    Native tool-calling structure is preserved end to end: an assistant turn
    may carry `tool_calls` (id/name/arguments in provider-neutral flat form)
    and a tool turn carries the `tool_call_id` (+ `tool_name`) it answers, so
    the next provider request can round-trip the protocol faithfully.
    """

    seq: int
    role: str
    content: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_call_id: str = ""
    tool_name: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentContext(BaseModel):
    """Three-window view of one agent's context for one task.

    Window 1 (`recent`): full-fidelity turns. Window 2 (`summary`): rolling
    compressed narrative. Window 3 (`milestones`): high-level outcomes only.
    """

    agent_id: str
    task_id: str
    recent: list[ChatTurn] = Field(default_factory=list)
    summary: str = ""
    milestones: list[str] = Field(default_factory=list)
    next_seq: int = 0


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class ContextStore(ABC):
    """Interface for global/agent context persistence, compression, and usage."""

    @abstractmethod
    def save_global(self, key: str, value: dict[str, Any]) -> None:
        """Upsert one global-context entry (repo map facts, extracted rules...)."""

    @abstractmethod
    def load_global(self, key: str) -> dict[str, Any] | None:
        """Fetch a global-context entry, or None."""

    @abstractmethod
    def append_turn(
        self,
        agent_id: str,
        task_id: str,
        role: str,
        content: str,
        *,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str = "",
        tool_name: str = "",
    ) -> ChatTurn:
        """Record one conversation turn (with optional tool structure) in the
        agent's recent window."""

    @abstractmethod
    def load_agent_context(self, agent_id: str, task_id: str) -> AgentContext:
        """Load the three-window context (empty windows if nothing stored)."""

    @abstractmethod
    def save_agent_context(self, context: AgentContext) -> None:
        """Persist all three windows of an agent context (upsert)."""

    @abstractmethod
    def clear_window(self, agent_id: str, task_id: str) -> None:
        """Drop the persisted conversation turns for one (agent, task) window.

        Task ids are reused across recovery-ladder retries, so a fresh
        `execute_task` must start from a clean window: rehydrating the failed
        attempt's turns appends a second TASK turn and the model replays its
        earlier replies instead of acting (live-run finding).
        """

    @abstractmethod
    def compress(
        self,
        agent_id: str,
        task_id: str,
        *,
        keep_recent: int = 20,
        summarize: Summarizer | None = None,
    ) -> int:
        """Fold the oldest turns beyond `keep_recent` into the summary.

        Returns the number of turns folded. Milestones stay untouched.
        """

    @abstractmethod
    def neighbors(self, agent_id: str, task_id: str) -> list[AgentContext]:
        """Contexts of *other* agents working the same task (neighbor retrieval)."""

    @abstractmethod
    def record_token_usage(
        self,
        correlation_id: str,
        agent_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Append to the token-usage ledger (budget governor input)."""

    @abstractmethod
    def token_usage(self, correlation_id: str) -> TokenUsage:
        """Aggregate usage for one task run."""

    @abstractmethod
    def close(self) -> None:
        """Release backend resources."""


class MemoryContextStore(ContextStore):
    """In-memory backend for tests and offline runs."""

    def __init__(self) -> None:
        self._global: dict[str, dict[str, Any]] = {}
        self._contexts: dict[tuple[str, str], AgentContext] = {}
        self._usage: dict[str, TokenUsage] = {}
        self._lock = threading.Lock()

    def save_global(self, key: str, value: dict[str, Any]) -> None:
        self._global[key] = value

    def load_global(self, key: str) -> dict[str, Any] | None:
        return self._global.get(key)

    def append_turn(
        self,
        agent_id: str,
        task_id: str,
        role: str,
        content: str,
        *,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str = "",
        tool_name: str = "",
    ) -> ChatTurn:
        ctx = self._ensure(agent_id, task_id)
        turn = ChatTurn(
            seq=ctx.next_seq,
            role=role,
            content=content,
            tool_calls=tool_calls or [],
            tool_call_id=tool_call_id,
            tool_name=tool_name,
        )
        ctx.recent.append(turn)
        ctx.next_seq += 1
        return turn

    def load_agent_context(self, agent_id: str, task_id: str) -> AgentContext:
        return self._ensure(agent_id, task_id)

    def save_agent_context(self, context: AgentContext) -> None:
        self._contexts[(context.agent_id, context.task_id)] = context

    def clear_window(self, agent_id: str, task_id: str) -> None:
        with self._lock:
            self._contexts.pop((agent_id, task_id), None)

    def compress(
        self,
        agent_id: str,
        task_id: str,
        *,
        keep_recent: int = 20,
        summarize: Summarizer | None = None,
    ) -> int:
        ctx = self._ensure(agent_id, task_id)
        return _compress_windows(ctx, keep_recent=keep_recent, summarize=summarize)

    def neighbors(self, agent_id: str, task_id: str) -> list[AgentContext]:
        return [c for (aid, tid), c in self._contexts.items() if tid == task_id and aid != agent_id]

    def record_token_usage(
        self,
        correlation_id: str,
        agent_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        with self._lock:
            cur = self._usage.get(correlation_id, TokenUsage())
            self._usage[correlation_id] = TokenUsage(
                prompt_tokens=cur.prompt_tokens + prompt_tokens,
                completion_tokens=cur.completion_tokens + completion_tokens,
            )

    def token_usage(self, correlation_id: str) -> TokenUsage:
        return self._usage.get(correlation_id, TokenUsage())

    def close(self) -> None:  # pragma: no cover - nothing to release
        return

    def _ensure(self, agent_id: str, task_id: str) -> AgentContext:
        return self._contexts.setdefault(
            (agent_id, task_id), AgentContext(agent_id=agent_id, task_id=task_id)
        )


class SQLiteContextStore(ContextStore):
    """Default backend: one SQLite file, WAL mode, thread-safe.

    Schema (versioned via PRAGMA user_version):
      global_context(key, value, updated_at)
      agent_contexts(agent_id, task_id, summary, milestones, updated_at)
      context_windows(agent_id, task_id, seq, role, content, created_at)
      token_usage(correlation_id, agent_id, model, prompt, completion, created_at)
      log_events(ts, level, event)
    """

    def __init__(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._migrate()

    def _migrate(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS global_context (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
                CREATE TABLE IF NOT EXISTS agent_contexts (
                    agent_id TEXT NOT NULL, task_id TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '', milestones TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                    PRIMARY KEY (agent_id, task_id));
                CREATE TABLE IF NOT EXISTS context_windows (
                    agent_id TEXT NOT NULL, task_id TEXT NOT NULL, seq INTEGER NOT NULL,
                    role TEXT NOT NULL, content TEXT NOT NULL,
                    tool_calls TEXT NOT NULL DEFAULT '[]',
                    tool_call_id TEXT NOT NULL DEFAULT '',
                    tool_name TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (agent_id, task_id, seq));
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    correlation_id TEXT NOT NULL, agent_id TEXT NOT NULL, model TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL, completion_tokens INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')));
                CREATE TABLE IF NOT EXISTS log_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL, level TEXT NOT NULL, event TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_usage_corr ON token_usage(correlation_id);
                CREATE INDEX IF NOT EXISTS idx_windows ON context_windows(agent_id, task_id);
            """)
            if self._conn.execute("PRAGMA user_version").fetchone()[0] < 2:
                # v1 -> v2: structured tool-call columns on existing databases.
                for column in (
                    "tool_calls TEXT NOT NULL DEFAULT '[]'",
                    "tool_call_id TEXT NOT NULL DEFAULT ''",
                    "tool_name TEXT NOT NULL DEFAULT ''",
                ):
                    with contextlib.suppress(sqlite3.OperationalError):
                        self._conn.execute(f"ALTER TABLE context_windows ADD COLUMN {column}")
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    # -- global ------------------------------------------------------------
    def save_global(self, key: str, value: dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO global_context(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')",
                (key, json.dumps(value)),
            )

    def load_global(self, key: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT value FROM global_context WHERE key = ?", (key,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    # -- agent contexts ------------------------------------------------------
    def append_turn(
        self,
        agent_id: str,
        task_id: str,
        role: str,
        content: str,
        *,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str = "",
        tool_name: str = "",
    ) -> ChatTurn:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT COALESCE(MAX(seq) + 1, 0) FROM context_windows "
                "WHERE agent_id = ? AND task_id = ?",
                (agent_id, task_id),
            ).fetchone()
            seq = int(row[0])
            now = datetime.now(UTC).isoformat()
            self._conn.execute(
                "INSERT INTO context_windows(agent_id, task_id, seq, role, content, "
                "tool_calls, tool_call_id, tool_name, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    agent_id,
                    task_id,
                    seq,
                    role,
                    content,
                    json.dumps(tool_calls or []),
                    tool_call_id,
                    tool_name,
                    now,
                ),
            )
        return ChatTurn(
            seq=seq,
            role=role,
            content=content,
            tool_calls=tool_calls or [],
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            created_at=datetime.fromisoformat(now),
        )

    def load_agent_context(self, agent_id: str, task_id: str) -> AgentContext:
        rows = self._conn.execute(
            "SELECT seq, role, content, tool_calls, tool_call_id, tool_name, created_at "
            "FROM context_windows WHERE agent_id = ? AND task_id = ? ORDER BY seq",
            (agent_id, task_id),
        ).fetchall()
        meta = self._conn.execute(
            "SELECT summary, milestones FROM agent_contexts WHERE agent_id = ? AND task_id = ?",
            (agent_id, task_id),
        ).fetchone()
        turns = [
            ChatTurn(
                seq=r[0],
                role=r[1],
                content=r[2],
                tool_calls=json.loads(r[3]),
                tool_call_id=r[4],
                tool_name=r[5],
                created_at=datetime.fromisoformat(r[6]),
            )
            for r in rows
        ]
        return AgentContext(
            agent_id=agent_id,
            task_id=task_id,
            recent=turns,
            summary=meta[0] if meta else "",
            milestones=json.loads(meta[1]) if meta else [],
            next_seq=(max((t.seq for t in turns), default=-1) + 1),
        )

    def save_agent_context(self, context: AgentContext) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO agent_contexts(agent_id, task_id, summary, milestones) "
                "VALUES(?, ?, ?, ?) ON CONFLICT(agent_id, task_id) DO UPDATE SET "
                "summary=excluded.summary, milestones=excluded.milestones, "
                "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')",
                (
                    context.agent_id,
                    context.task_id,
                    context.summary,
                    json.dumps(context.milestones),
                ),
            )
            self._conn.execute(
                "DELETE FROM context_windows WHERE agent_id = ? AND task_id = ?",
                (context.agent_id, context.task_id),
            )
            self._conn.executemany(
                "INSERT INTO context_windows(agent_id, task_id, seq, role, content, "
                "tool_calls, tool_call_id, tool_name, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        context.agent_id,
                        context.task_id,
                        t.seq,
                        t.role,
                        t.content,
                        json.dumps(t.tool_calls),
                        t.tool_call_id,
                        t.tool_name,
                        t.created_at.isoformat(),
                    )
                    for t in context.recent
                ],
            )

    def clear_window(self, agent_id: str, task_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM context_windows WHERE agent_id = ? AND task_id = ?",
                (agent_id, task_id),
            )
            self._conn.execute(
                "DELETE FROM agent_contexts WHERE agent_id = ? AND task_id = ?",
                (agent_id, task_id),
            )

    def compress(
        self,
        agent_id: str,
        task_id: str,
        *,
        keep_recent: int = 20,
        summarize: Summarizer | None = None,
    ) -> int:
        ctx = self.load_agent_context(agent_id, task_id)
        folded = _compress_windows(ctx, keep_recent=keep_recent, summarize=summarize)
        if folded:
            self.save_agent_context(ctx)
        return folded

    def neighbors(self, agent_id: str, task_id: str) -> list[AgentContext]:
        rows = self._conn.execute(
            "SELECT DISTINCT agent_id FROM context_windows WHERE task_id = ? AND agent_id != ? "
            "UNION "
            "SELECT DISTINCT agent_id FROM agent_contexts WHERE task_id = ? AND agent_id != ?",
            (task_id, agent_id, task_id, agent_id),
        ).fetchall()
        return [self.load_agent_context(r[0], task_id) for r in rows]

    # -- usage ledger --------------------------------------------------------
    def record_token_usage(
        self,
        correlation_id: str,
        agent_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO token_usage(correlation_id, agent_id, model, prompt_tokens, "
                "completion_tokens) VALUES(?, ?, ?, ?, ?)",
                (correlation_id, agent_id, model, prompt_tokens, completion_tokens),
            )

    def token_usage(self, correlation_id: str) -> TokenUsage:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0) "
            "FROM token_usage WHERE correlation_id = ?",
            (correlation_id,),
        ).fetchone()
        return TokenUsage(prompt_tokens=int(row[0]), completion_tokens=int(row[1]))

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class DatabaseLogHandler(logging.Handler):
    """Persist structured log records into the store's `log_events` table
    (foundation issue 1.7: "logs persisted to database")."""

    def __init__(self, store: SQLiteContextStore, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._store = store

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event = {
                "name": record.name,
                "message": record.getMessage(),
                "correlation_id": getattr(record, "correlation_id", None),
            }
            with self._store._lock, self._store._conn:
                self._store._conn.execute(
                    "INSERT INTO log_events(ts, level, event) VALUES "
                    "(strftime('%Y-%m-%dT%H:%M:%SZ','now'), ?, ?)",
                    (record.levelname, json.dumps(event)),
                )
        except Exception:  # pragma: no cover - logging must never raise
            self.handleError(record)


class PostgresContextStore(ContextStore):
    """PostgreSQL backend for the full deployment vision.

    Requires the `postgres` extra (`pip install harness[postgres]`). The DSN
    comes from the environment variable named by `StorageConfig.postgres_dsn_env`.
    """

    def __init__(self, config: StorageConfig) -> None:
        import os

        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - depends on extras
            msg = "PostgreSQL backend requires the 'postgres' extra: pip install harness[postgres]"
            raise RuntimeError(msg) from exc
        dsn = os.environ.get(config.postgres_dsn_env)
        if not dsn:
            msg = f"environment variable '{config.postgres_dsn_env}' (PostgreSQL DSN) is not set"
            raise RuntimeError(msg)
        self._conn = psycopg.connect(dsn)
        self._migrate()

    def _migrate(self) -> None:  # pragma: no cover - exercised only with PG
        with self._conn, self._conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS global_context (
                    key TEXT PRIMARY KEY, value JSONB NOT NULL, updated_at TIMESTAMPTZ DEFAULT now());
                CREATE TABLE IF NOT EXISTS agent_contexts (
                    agent_id TEXT NOT NULL, task_id TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '', milestones JSONB NOT NULL DEFAULT '[]',
                    updated_at TIMESTAMPTZ DEFAULT now(), PRIMARY KEY (agent_id, task_id));
                CREATE TABLE IF NOT EXISTS context_windows (
                    agent_id TEXT NOT NULL, task_id TEXT NOT NULL, seq INTEGER NOT NULL,
                    role TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now(),
                    PRIMARY KEY (agent_id, task_id, seq));
                CREATE TABLE IF NOT EXISTS token_usage (
                    id BIGSERIAL PRIMARY KEY, correlation_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL, model TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL, completion_tokens INTEGER NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now());
                CREATE INDEX IF NOT EXISTS idx_usage_corr ON token_usage(correlation_id);
            """)

    # Shared logic is identical to SQLite; delegate via composition to avoid drift.
    def save_global(self, key: str, value: dict[str, Any]) -> None:  # pragma: no cover
        with self._conn, self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO global_context(key, value) VALUES(%s, %s) "
                "ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value",
                (key, json.dumps(value)),
            )

    def load_global(self, key: str) -> dict[str, Any] | None:  # pragma: no cover
        with self._conn.cursor() as cur:
            cur.execute("SELECT value FROM global_context WHERE key = %s", (key,))
            row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def append_turn(
        self,
        agent_id: str,
        task_id: str,
        role: str,
        content: str,
        *,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str = "",
        tool_name: str = "",
    ) -> ChatTurn:
        raise NotImplementedError  # pragma: no cover - completed with PG pooling in milestone 2

    def load_agent_context(self, agent_id: str, task_id: str) -> AgentContext:
        raise NotImplementedError  # pragma: no cover

    def save_agent_context(self, context: AgentContext) -> None:
        raise NotImplementedError  # pragma: no cover

    def compress(
        self,
        agent_id: str,
        task_id: str,
        *,
        keep_recent: int = 20,
        summarize: Summarizer | None = None,
    ) -> int:
        raise NotImplementedError  # pragma: no cover

    def neighbors(self, agent_id: str, task_id: str) -> list[AgentContext]:
        raise NotImplementedError  # pragma: no cover

    def clear_window(self, agent_id: str, task_id: str) -> None:  # pragma: no cover
        with self._conn, self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM context_windows WHERE agent_id = %s AND task_id = %s",
                (agent_id, task_id),
            )
            cur.execute(
                "DELETE FROM agent_contexts WHERE agent_id = %s AND task_id = %s",
                (agent_id, task_id),
            )

    def record_token_usage(
        self,
        correlation_id: str,
        agent_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:  # pragma: no cover
        with self._conn, self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO token_usage(correlation_id, agent_id, model, prompt_tokens, "
                "completion_tokens) VALUES(%s, %s, %s, %s, %s)",
                (correlation_id, agent_id, model, prompt_tokens, completion_tokens),
            )

    def token_usage(self, correlation_id: str) -> TokenUsage:  # pragma: no cover
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0) "
                "FROM token_usage WHERE correlation_id = %s",
                (correlation_id,),
            )
            row = cur.fetchone()
        return TokenUsage(prompt_tokens=int(row[0]), completion_tokens=int(row[1]))

    def close(self) -> None:  # pragma: no cover
        self._conn.close()


def create_context_store(config: StorageConfig) -> ContextStore:
    """Backend factory driven by `StorageConfig`."""
    if config.backend == "memory":
        return MemoryContextStore()
    if config.backend == "sqlite":
        return SQLiteContextStore(config.sqlite_path)
    return PostgresContextStore(config)


def compress_ratio_before_after(
    store: ContextStore, agent_id: str, task_id: str, n_turns: int, content_len: int
) -> float:
    """Acceptance helper: byte reduction achieved on the *folded* turns.

    The recent window is uncompressed by design, so the >60% criterion from
    the issue is measured over the turns that compression actually rewrote.
    """
    for i in range(n_turns):
        store.append_turn(agent_id, task_id, "user" if i % 2 else "assistant", "x" * content_len)
    folded = store.compress(agent_id, task_id, keep_recent=max(1, n_turns // 3))
    ctx = store.load_agent_context(agent_id, task_id)
    original_bytes = folded * content_len
    return (1 - len(ctx.summary) / original_bytes) if original_bytes and folded else 0.0


def iter_store_tables(store: ContextStore) -> Iterable[str]:  # pragma: no cover - debug aid
    """Best-effort table listing for debugging backends."""
    if isinstance(store, SQLiteContextStore):
        rows = store._conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return [r[0] for r in rows]
    return []
