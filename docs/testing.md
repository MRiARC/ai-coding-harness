# Testing Guide

## Running

```bash
make test        # pytest with coverage (offline - no API key, no network)
make lint        # ruff check + format check
make typecheck   # mypy
```

`pytest` is configured (see `pyproject.toml`) with coverage reporting enabled
by default. Tests never touch the network: model calls go through
`FakeProvider`, GitHub calls through `httpx.MockTransport`.

## Writing tests

- **Async tests**: decorate with `@pytest.mark.anyio` (the `anyio_backend`
  fixture in `conftest.py` pins asyncio).
- **Backend-parametrized stores**: use the `store` fixture to run a test
  against both the in-memory and SQLite context stores.
- **Scripted model**: `make_fake_provider(*script)` returns a provider that
  replays `ModelResponse`s (or raises the scripted `Exception`s). Exhausting
  the script fails loudly - extend it rather than ignoring calls.
- **Mock GitHub**: `mock_github({"/issues": {...}})` answers REST calls from a
  path-suffix map; `mock_github.captured` exposes the requests for assertions.
  Use `github_offline` to assert the graceful no-credentials behavior.
- **Scratch repos**: the `git_repo` fixture gives you an initialized temp
  repository for branch/diff/commit flows.
- **CLI**: use `isolated_env` (empty cwd, no `AI_API_KEY`) and call
  `harness.cli.main([...])` directly.

## What must stay true

1. Tests are deterministic: no sleeps (use `extra={"backoff_base_seconds": 0.001}`),
   no network, no filesystem outside `tmp_path`.
2. Every infrastructure seam is mockable by construction (provider `client`
   injection, `ContextStore` backends, `GitHubService` client injection).
3. Coverage stays meaningful: `pytest --cov-report=term-missing` shows gaps;
   keep the evidence-critical paths (store, budget, recovery) well covered.
