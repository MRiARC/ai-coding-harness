"""Example integration test: the milestone-1 skeleton wired end to end.

Demonstrates the pattern the agent loop (milestone 2) will follow:
config -> context store -> model provider -> usage ledger -> evidence dir.
Runs fully offline via the FakeProvider.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness.infrastructure.context_store import create_context_store
from harness.infrastructure.model_providers import ModelResponse, ToolCall


async def test_single_turn_pipeline_skeleton(sample_config, tmp_path: Path) -> None:
    # 1. context store from config
    store = create_context_store(sample_config.storage)

    # 2. record the agent's observation of the task
    correlation_id = "corr-int-1"
    store.append_turn("implementer-1", "task-1", "user", "issue: parser crashes on empty input")

    # 3. scripted model call (no network, no key)
    from harness.infrastructure.model_providers import create_model_provider

    provider = create_model_provider(sample_config.models["default"])
    assert provider.name == "fake"
    provider._responses.append(
        ModelResponse(
            content="I will read parser.py",
            tool_calls=[ToolCall(name="read_file", arguments={"path": "parser.py"})],
        )
    )
    response = await provider.generate([{"role": "user", "content": "fix it"}])
    assert response.tool_calls[0].name == "read_file"

    # 4. usage lands in the ledger (budget governor input)
    store.record_token_usage(
        correlation_id,
        "implementer-1",
        provider.model,
        response.prompt_tokens,
        response.completion_tokens,
    )
    usage = store.token_usage(correlation_id)
    assert usage.total_tokens > 0

    # 5. evidence pack skeleton on disk
    results = tmp_path / sample_config.run.results_dir / correlation_id
    results.mkdir(parents=True)
    (results / "trace.jsonl").write_text(
        json.dumps(
            {"event": "model_response", "tool": "read_file", "correlation_id": correlation_id}
        )
        + "\n"
    )
    lines = (results / "trace.jsonl").read_text().splitlines()
    assert json.loads(lines[0])["correlation_id"] == correlation_id
    store.close()
