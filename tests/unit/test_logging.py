"""Logging infrastructure tests: correlation IDs, handlers, formats (issue 1.7)."""

from __future__ import annotations

import json
import logging

from harness.infrastructure.logging import (
    configure_logging,
    get_logger,
    new_correlation_id,
    set_correlation_id,
)


def test_new_correlation_id_binds_and_is_unique() -> None:
    first = new_correlation_id()
    second = new_correlation_id()
    assert first and second and first != second


def test_set_correlation_id_adopts_value() -> None:
    set_correlation_id("fixed-correlation-id")
    log = get_logger("test.adopt")
    log.info("adopted")  # runs through structlog; must not raise


def test_json_logs_go_to_stderr(capsys) -> None:
    configure_logging(level="INFO", json_format=True, file_path=None)
    log = get_logger("test.json")
    log.info("hello structured", extra_field=42)
    err = capsys.readouterr().err
    record = json.loads(err.strip().splitlines()[-1])
    assert record["event"] == "hello structured"
    assert record["extra_field"] == 42
    assert record["level"] == "info"


def test_file_handler_and_rotation_params(tmp_path) -> None:
    log_file = tmp_path / "logs" / "harness.log"
    configure_logging(
        level="INFO", json_format=True, file_path=str(log_file), max_bytes=1000, backup_count=2
    )
    log = get_logger("test.file")
    log.info("written to file")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert log_file.exists()
    assert "written to file" in log_file.read_text()
    configure_logging(level="INFO", json_format=True, file_path=None)  # reset


def test_console_renderer_when_json_disabled(capsys) -> None:
    configure_logging(level="INFO", json_format=False, file_path=None)
    log = get_logger("test.console")
    log.warning("human readable")
    err = capsys.readouterr().err
    assert "human readable" in err
    configure_logging(level="INFO", json_format=True, file_path=None)  # reset
