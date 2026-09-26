"""M5 tool additions: filesystem_write (creation hand), glob_files, git_add.

The create-app capability trio: `apply_edit` can only modify existing files,
new files never reached `git diff HEAD` (untracked), and there was no
pattern-matching file listing. These tools close all three gaps.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.tools.filesystem import GlobTool, WriteFileTool
from harness.tools.vcs import GitAddTool


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "existing.py").write_text("VALUE = 1\n")
    return tmp_path


# -- filesystem_write -------------------------------------------------------


def test_write_create_new_file(repo: Path) -> None:
    tool = WriteFileTool(repo)
    result = tool.execute(path="src/new.py", content="VALUE = 2\n")
    assert result.success
    assert (repo / "src" / "new.py").read_text() == "VALUE = 2\n"
    assert result.data == {"path": "src/new.py", "mode": "create", "existed_before": False}


def test_write_create_refuses_to_clobber(repo: Path) -> None:
    tool = WriteFileTool(repo)
    result = tool.execute(path="src/existing.py", content="VALUE = 99\n", mode="create")
    assert not result.success
    assert "already exists" in (result.error or "")
    assert (repo / "src" / "existing.py").read_text() == "VALUE = 1\n"


def test_write_overwrite_keeps_backup(repo: Path) -> None:
    tool = WriteFileTool(repo)
    result = tool.execute(path="src/existing.py", content="VALUE = 2\n", mode="overwrite")
    assert result.success and result.data["existed_before"] is True
    assert (repo / "src" / "existing.py").read_text() == "VALUE = 2\n"
    backup = repo / ".harness" / "backups" / "existing.py.bak"
    assert backup.read_text() == "VALUE = 1\n"


def test_write_append_existing_only(repo: Path) -> None:
    tool = WriteFileTool(repo)
    ok = tool.execute(path="src/existing.py", content="VALUE = 2\n", mode="append")
    assert ok.success
    assert (repo / "src" / "existing.py").read_text() == "VALUE = 1\nVALUE = 2\n"
    missing = tool.execute(path="src/absent.py", content="x", mode="append")
    assert not missing.success
    assert "use mode='create'" in (missing.error or "")


def test_write_rejects_bad_mode_and_oversize(repo: Path) -> None:
    tool = WriteFileTool(repo)
    assert tool.validate_input({"path": "x", "content": "", "mode": "delete"})
    oversize = tool.execute(path="big.py", content="x" * (tool.MAX_WRITE_BYTES + 1))
    assert not oversize.success
    assert "write cap" in (oversize.error or "")
    outside = tool.execute(path="../escape.py", content="x")
    assert not outside.success


# -- glob_files ---------------------------------------------------------------


def test_glob_matches_and_skips_junk(repo: Path) -> None:
    (repo / "src" / "more.py").write_text("x = 1\n")
    (repo / "src" / "junk.pyc").write_text("binary")
    tool = GlobTool(repo)
    result = tool.execute(pattern="**/*.py")
    assert result.success
    assert "src/existing.py" in result.output and "src/more.py" in result.output
    assert ".pyc" not in result.output


def test_glob_capped_and_scoped_and_empty(repo: Path) -> None:
    for i in range(5):
        (repo / "src" / f"f{i}.py").write_text("x\n")
    tool = GlobTool(repo)
    scoped = tool.execute(pattern="*.py", path="src")
    assert scoped.success and "src/f0.py" in scoped.output
    empty = tool.execute(pattern="*.rs")
    assert empty.success and "no files match" in empty.output
    assert tool.validate_input({}) == ["'pattern' is required"]
    bad = tool.execute(pattern="*.py", path="../outside")
    assert not bad.success


# -- git_add ------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    import subprocess

    (repo / "README.md").write_text("scratch repo\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-qm", "base"], check=True, capture_output=True
    )


def test_git_add_intent_to_add_makes_new_file_visible(tmp_path: Path) -> None:
    """The whole point: an untracked new file must appear in git diff HEAD."""
    _git_init(tmp_path)
    (tmp_path / "created.py").write_text("NEW = 1\n")
    tool = GitAddTool(tmp_path)
    result = tool.execute(paths=["created.py"])
    assert result.success
    diff = (
        __import__("subprocess")
        .run(["git", "diff", "HEAD"], cwd=tmp_path, capture_output=True, text=True)
        .stdout
    )
    assert "created.py" in diff and "NEW = 1" in diff


def test_git_add_all_and_validation(tmp_path: Path) -> None:
    _git_init(tmp_path)
    (tmp_path / "a.py").write_text("A = 1\n")
    (tmp_path / "b.py").write_text("B = 1\n")
    tool = GitAddTool(tmp_path)
    assert tool.validate_input({})  # neither paths nor all -> error list
    assert tool.validate_input({"all": True}) == []  # the all-path early return
    ok = tool.execute(all=True)
    assert ok.success
    assert tool.validate_input({"paths": ["a.py", "b.py"]}) == []
    assert tool.validate_input({"paths": "a.py"})  # not a list


def test_git_add_outside_repo_fails_gracefully(tmp_path: Path) -> None:
    tool = GitAddTool(tmp_path)
    result = tool.execute(all=True)
    assert not result.success  # not a git repository


def test_write_validate_input_and_write_oserror(repo: Path, monkeypatch) -> None:
    tool = WriteFileTool(repo)
    assert tool.validate_input({"path": "", "content": "x"})  # empty path
    assert tool.validate_input({"path": "x", "content": 5})  # non-str content
    assert tool.validate_input({"path": "x", "content": "x", "mode": "weird"})

    real_open = Path.open

    def boom(self, *args, **kwargs):
        raise OSError("disk gone")

    monkeypatch.setattr(Path, "open", boom)
    result = tool.execute(path="src/whatever.py", content="x")
    assert not result.success and "cannot write" in (result.error or "")
    del real_open


def test_glob_skips_harness_dirs_and_validate(repo: Path) -> None:
    (repo / ".harness").mkdir()
    (repo / ".harness" / "secret.py").write_text("s = 1\n")
    (repo / ".venv").mkdir()
    (repo / ".venv" / "v.py").write_text("v = 1\n")
    tool = GlobTool(repo)
    result = tool.execute(pattern="**/*.py")
    assert ".harness" not in result.output and ".venv" not in result.output
    assert "src/existing.py" in result.output  # real files still listed


def test_glob_non_directory_root(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("x")
    tool = GlobTool(tmp_path)
    result = tool.execute(pattern="*.py", path="file.txt")
    assert not result.success and "not a directory" in (result.error or "")


def test_git_add_validate_paths_non_string(tmp_path: Path) -> None:
    tool = GitAddTool(tmp_path)
    assert tool.validate_input({"paths": [1, 2]})


def test_glob_skips_directories_named_like_files(repo: Path) -> None:
    """rglob matches dirs too: a directory named `weird.py` is skipped."""
    (repo / "src" / "weird.py").mkdir()
    (repo / "src" / "weird.py" / "inner.txt").write_text("x")
    (repo / "src" / "junk.pyc.py").write_text(
        "compiled? no: text with .pyc suffix check is on suffix only"
    )
    tool = GlobTool(repo)
    result = tool.execute(pattern="**/*weird*")
    assert result.success and result.output.strip() == "no files match '**/*weird*'"


def test_glob_output_capped_at_max(repo: Path) -> None:
    """MAX_MATCHES cap: a wide pattern lists the cap and stops."""
    tool = GlobTool(repo)
    for i in range(tool.MAX_MATCHES + 10):
        (repo / "src" / f"g{i}.py").write_text("x\n")
    result = tool.execute(pattern="g*.py", path="src")
    assert result.success
    assert f"capped at {tool.MAX_MATCHES} files" in result.output
    assert len(result.output.splitlines()) == tool.MAX_MATCHES + 1
