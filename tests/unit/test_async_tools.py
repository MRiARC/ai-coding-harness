"""Milestone 4.5: awaitable subprocess tools (audit §22).

Long-running tools must not block the event loop while parallel specialists
work: the agent loop and pipeline await `execute_async`, and concurrent
invocations overlap instead of serializing.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import field
from pathlib import Path

import pytest

from harness.config import ModelConfig
from harness.tools.base import ToolResult, ToolTier
from harness.tools.execution import CodeExecutionTool, RunTestsTool


@pytest.fixture
def pytest_repo(tmp_path: Path) -> Path:
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    return tmp_path


async def test_run_tests_async_passes(pytest_repo: Path) -> None:
    tool = RunTestsTool(pytest_repo)
    result = await tool.execute_async()
    assert result.success
    assert result.data["framework"] == "pytest"


async def test_run_tests_async_path_subset(pytest_repo: Path) -> None:
    """The optional pytest path subset is appended to the detected command."""
    tool = RunTestsTool(pytest_repo)
    result = await tool.execute_async(path="test_ok.py")
    assert result.success


async def test_run_tests_async_reports_failures(pytest_repo: Path) -> None:
    (pytest_repo / "test_bad.py").write_text("def test_bad():\n    assert False\n")
    tool = RunTestsTool(pytest_repo)
    result = await tool.execute_async()
    assert not result.success
    assert "tests failed" in (result.error or "")


async def test_run_tests_async_no_runner(tmp_path: Path) -> None:
    tool = RunTestsTool(tmp_path)
    result = await tool.execute_async()
    assert not result.success
    assert "no test runner detected" in (result.error or "")


async def test_code_execution_async_success(tmp_path: Path) -> None:
    tool = CodeExecutionTool(tmp_path)
    result = await tool.execute_async(command=["python", "-c", "print('async-ok')"])
    assert result.success
    assert "async-ok" in result.output


async def test_code_execution_async_failure_exit_code(tmp_path: Path) -> None:
    tool = CodeExecutionTool(tmp_path)
    result = await tool.execute_async(command=["python", "-c", "raise SystemExit(3)"])
    assert not result.success
    assert "exit 3" in (result.error or "")


async def test_code_execution_async_timeout(tmp_path: Path) -> None:
    tool = CodeExecutionTool(tmp_path, timeout=0.5)
    result = await tool.execute_async(command=["python", "-c", "import time; time.sleep(5)"])
    assert not result.success
    assert "sandbox timeout" in (result.error or "")


async def test_concurrent_async_tools_overlap(tmp_path: Path) -> None:
    """Two 0.6s subprocesses run concurrently (audit §22: no event-loop
    serialization); sequential execution would take >= 1.2s."""
    tool = CodeExecutionTool(tmp_path)
    sleep_script = ["python", "-c", "import time; time.sleep(0.6)"]
    started = time.monotonic()
    results = await asyncio.gather(*(tool.execute_async(command=sleep_script) for _ in range(2)))
    elapsed = time.monotonic() - started
    assert all(r.success for r in results)
    assert elapsed < 1.2, f"concurrent tools serialized: {elapsed:.2f}s"


async def test_agent_loop_awaits_async_tool(tmp_path: Path) -> None:
    """The agent loop routes async tools through execute_async."""
    from harness.agents.llm_agent import LLMAgent, StoreWindow
    from harness.agents.task import Task
    from harness.config import BudgetConfig
    from harness.engine.budget import BudgetGovernor
    from harness.infrastructure.context_store import MemoryContextStore
    from harness.infrastructure.model_providers.base import ModelResponse, ToolCall
    from harness.infrastructure.model_providers.fake import FakeProvider

    config_code = ModelConfig(provider="fake", name="fake-model", api_key_env="AI_API_KEY")
    provider = FakeProvider(
        config_code,
        responses=[
            ModelResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        id="c1",
                        name="code_execution",
                        arguments={"command": ["python", "-c", "print('loop-ok')"]},
                    )
                ],
            ),
            ModelResponse(content="TASK_COMPLETE: ran the command"),
        ],
    )
    store = MemoryContextStore()
    agent = LLMAgent(
        agent_id="impl-1",
        model_config={},
        tools=[CodeExecutionTool(tmp_path)],
        context_window=StoreWindow(store, "impl-1", "task-1"),
        provider=provider,
        store=store,
        governor=BudgetGovernor(store, BudgetConfig(), "run-1"),
        role="devops",  # ADVANCED tier preset allows code_execution
        model_tier=3,
    )
    result = await agent.execute_task(
        Task(id="task-1", title="Run", description="Execute a command.")
    )
    assert result.success
    window = store.load_agent_context("impl-1", "task-1").recent
    tool_turn = next(t for t in window if t.role == "tool")
    assert "loop-ok" in tool_turn.content
    assert tool_turn.tool_call_id == "c1"


async def test_async_base_default_raises() -> None:
    """A concrete tool that skips execute_async hits the base guard."""
    from harness.tools.base import AsyncExecutableTool

    class Bare(AsyncExecutableTool):
        name, tier = "bare", ToolTier.BASIC
        description = "bare"
        parameters: dict = field(default_factory=dict)

        def validate_input(self, arguments):
            return []

        def check_permissions(self, context):
            return True

        def execute(self, **kwargs):
            return ToolResult(success=True)

    with pytest.raises(NotImplementedError):
        await Bare().execute_async()


async def test_run_tests_spawn_oserror_after_detection(tmp_path: Path, monkeypatch) -> None:
    """Spawn failure after successful runner detection returns a clear error."""
    import asyncio as aio

    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    tool = RunTestsTool(tmp_path, timeout=1.0)

    async def _raise(*args, **kwargs):
        raise OSError("no binaries in this desert")

    monkeypatch.setattr(aio, "create_subprocess_exec", _raise)
    result = await tool.execute_async()
    assert not result.success
    assert "cannot spawn test runner" in (result.error or "")


async def test_run_tests_async_timeout_kills_child(tmp_path: Path) -> None:
    """A hung suite times out and the child is killed (no silent wait)."""
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "test_slow.py").write_text("import time\n\ndef test_slow():\n    time.sleep(5)\n")
    tool = RunTestsTool(tmp_path, timeout=0.5)
    started = time.monotonic()
    result = await tool.execute_async()
    elapsed = time.monotonic() - started
    assert not result.success
    assert "timeout" in (result.error or "")
    assert elapsed < 3


async def test_code_execution_async_spawn_oserror(tmp_path: Path, monkeypatch) -> None:
    import asyncio as aio

    tool = CodeExecutionTool(tmp_path)

    async def _raise(*args, **kwargs):
        raise OSError("spawn refused")

    monkeypatch.setattr(aio, "create_subprocess_exec", _raise)
    result = await tool.execute_async(command=["python", "-c", "pass"])
    assert not result.success
    assert "cannot spawn command" in (result.error or "")
