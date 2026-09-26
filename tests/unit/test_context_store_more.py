"""Extended context-store tests: factory dispatch, log sink, PG guards (issues 1.4/1.7)."""

from __future__ import annotations

import logging
import sys
import types

import pytest

from harness.config import StorageConfig
from harness.infrastructure.context_store import (
    DatabaseLogHandler,
    PostgresContextStore,
    SQLiteContextStore,
    create_context_store,
    iter_store_tables,
)


def test_factory_sqlite_dispatch(tmp_path) -> None:
    store = create_context_store(
        StorageConfig(backend="sqlite", sqlite_path=str(tmp_path / "c.db"))
    )
    assert isinstance(store, SQLiteContextStore)
    store.close()


def test_factory_postgres_fallthrough(tmp_path, monkeypatch) -> None:
    """backend='postgres' constructs PostgresContextStore (guards tested below)."""
    fake_psycopg = types.ModuleType("psycopg")
    fake_psycopg.connect = lambda dsn: (_ for _ in ()).throw(AssertionError("should not connect"))
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setenv("HARNESS_POSTGRES_DSN", "")  # falsy DSN -> guard fires
    with pytest.raises(RuntimeError, match="HARNESS_POSTGRES_DSN"):
        PostgresContextStore(StorageConfig(backend="postgres"))


def test_factory_postgres_dispatch_connects_and_migrates(tmp_path, monkeypatch) -> None:
    """With psycopg importable and a DSN set, the factory builds the PG store."""

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql):
            self.sql = sql

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return FakeCursor()

        def close(self):
            pass

    fake_psycopg = types.ModuleType("psycopg")
    fake_psycopg.connect = lambda dsn: FakeConn()
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setenv("HARNESS_POSTGRES_DSN", "postgres://fake")
    store = create_context_store(StorageConfig(backend="postgres"))
    assert isinstance(store, PostgresContextStore)
    store.close()


def test_postgres_requires_extra_when_psycopg_missing(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "psycopg", raising=False)
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "psycopg":
            raise ImportError("no psycopg here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match=r"postgres.*extra"):
        PostgresContextStore(StorageConfig(backend="postgres"))


def test_database_log_handler_persists_and_scopes_levels(tmp_path) -> None:
    store = SQLiteContextStore(tmp_path / "ctx.db")
    handler = DatabaseLogHandler(store, level=logging.WARNING)  # scoped level
    log = logging.getLogger("test.sink")
    log.setLevel(logging.INFO)
    log.addHandler(handler)
    try:
        log.info("dropped below level")
        log.warning("kept %s", "one")
        log.error("kept two")
    finally:
        log.removeHandler(handler)
    rows = store._conn.execute("SELECT level, event FROM log_events").fetchall()
    assert [r[0] for r in rows] == ["WARNING", "ERROR"]
    assert "kept one" in rows[0][1]
    store.close()


def test_iter_store_tables_lists_schema(tmp_path) -> None:
    store = SQLiteContextStore(tmp_path / "ctx.db")
    tables = set(iter_store_tables(store))
    assert {
        "global_context",
        "agent_contexts",
        "context_windows",
        "token_usage",
        "log_events",
    } <= tables
    store.close()


def test_iter_store_tables_tolerates_memory_store() -> None:
    from harness.infrastructure.context_store import MemoryContextStore

    assert iter_store_tables(MemoryContextStore()) == []


def test_factory_memory_dispatch() -> None:
    from harness.infrastructure.context_store import MemoryContextStore

    store = create_context_store(StorageConfig(backend="memory"))
    assert isinstance(store, MemoryContextStore)
    store.close()
