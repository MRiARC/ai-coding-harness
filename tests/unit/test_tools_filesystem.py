"""Tier-1 filesystem tools + repo summary (issue 3.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.tools.filesystem import ListDirTool, ReadFileTool, summarize_repository


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("line one\nline two\nline three\n")
    (tmp_path / "README.md").write_text("# demo\n")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "junk.py").write_text("x = 1\n")
    return tmp_path


def test_read_file_full(repo) -> None:
    result = ReadFileTool(repo).execute(path="src/app.py")
    assert result.success
    assert "1| line one" in result.output and "3| line three" in result.output
    assert result.data["lines"] == 3


def test_read_file_range(repo) -> None:
    result = ReadFileTool(repo).execute(path="src/app.py", start_line=2, end_line=3)
    assert "2| line two" in result.output
    assert "line one" not in result.output


def test_read_file_missing_and_validation(repo) -> None:
    tool = ReadFileTool(repo)
    assert tool.validate_input({}) != []
    assert tool.validate_input({"path": "x", "start_line": 0}) != []
    assert tool.validate_input({"path": "x", "start_line": 2}) == []
    result = tool.execute(path="src/ghost.py")
    assert not result.success and "not a file" in result.error
    assert not tool.execute(path="src").success  # directory, not a file


def test_read_file_traversal_blocked(repo) -> None:
    result = ReadFileTool(repo).execute(path="../outside.py")
    assert not result.success and "escapes" in result.error
    assert not ReadFileTool(repo).execute(path="/etc/passwd").success


def test_read_file_truncation(repo, monkeypatch) -> None:
    import harness.tools.filesystem as fs

    monkeypatch.setattr(fs, "MAX_READ_BYTES", 10)
    (repo / "big.txt").write_text("A" * 500)
    result = ReadFileTool(repo).execute(path="big.txt")
    assert "truncated at 10 bytes" in result.output


def test_list_dir(repo) -> None:
    result = ListDirTool(repo).execute()
    assert "src/" in result.output and "README.md" in result.output
    assert ".venv" not in result.output  # skipped
    assert result.data["count"] == 2


def test_list_dir_subdirectory_and_errors(repo) -> None:
    result = ListDirTool(repo).execute(path="src")
    assert "app.py" in result.output
    assert not ListDirTool(repo).execute(path="src/app.py").success
    assert not ListDirTool(repo).execute(path="../..").success


def test_summarize_repository(repo) -> None:
    summary = summarize_repository(repo)
    assert summary["total_files"] == 2  # .venv content skipped
    assert summary["extensions"][".py"] == 1
    assert "src" in summary["top_level"] and "README.md" in summary["top_level"]
