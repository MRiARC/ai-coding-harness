# Live Agent Verification — 5-Configured-Agent Sweep

**Date:** 2026-09-26 · **Runner:** automated review (ZCode), temp dir `/tmp/harness-review/`
**Target:** every agent configured in `config.example.yaml` (architect-1, manager-1, locator-1, implementer-1, verifier-1) called through the real `harness.infrastructure.model_providers` stack against the live model endpoint.

## Verdict: ✅ 6/6 passed (5 agent pings + 1 tool-calling round-trip)

| Agent | Role | Result | Reply snippet |
|---|---|---|---|
| architect-1 | architect | ✅ 200, stop | "I am the architect agent … fully operational." |
| manager-1 | manager | ✅ 200, stop | *(see caveat B)* "I'm Kiro … operational" |
| locator-1 | locator | ✅ 200, stop | "I am the locator agent, specialized in navigating codebases…" |
| implementer-1 | implementer | ✅ 200, stop | *(see caveat B)* "I'm Kiro … operational" |
| verifier-1 | verifier | ✅ 200, stop | "I am the verifier agent responsible for validating code changes…" |
| tool-call check | implementer | ✅ 200, `stop_reason: tool_calls` | emitted valid `list_files` tool call — the loop-critical path works |

Per-call usage ≈ 4.4–5.0k prompt tokens / 20–31 completion tokens; model echoed back as `claude-sonnet-4.5`; retries never triggered; auth fast-fail path previously validated (401s surface as `ModelAuthError` without retry burn).

## Endpoint & model facts (supersedes earlier assumptions)

- The key belongs to a **local gateway** (`http://127.0.0.1:5580`, "kiro-api" proxy, 15 accounts) speaking the **OpenAI chat-completions wire protocol** at `/v1/chat/completions` — *not* the native Anthropic Messages API, and *not* api.openai.com (both official endpoints reject the key).
- **There is no `claude-sonnet-5` on this gateway.** Newest Sonnet is **`claude-sonnet-4.5`** (used for this sweep); also available: `claude-opus-4.5`, `claude-sonnet-4`, `claude-3.7-sonnet`, `claude-haiku-4.5`, `gpt-4o` family, plus internal-style IDs (`CLAUDE_SONNET_4_20250514_V1_0`…) and `auto`/`simple-task`. All report `tool_call: true`, 200k context.
- Harness config mapping: `provider: openai-compatible`, `base_url: http://127.0.0.1:5580/v1`, `name: claude-sonnet-4.5`, `api_key_env: AI_API_KEY` (key read from the environment; never committed).

## Caveats to watch

- **A. Prompt-token overhead:** ~4.4k prompt tokens for a ~30-token conversation indicates the gateway injects a large upstream system prompt. At eval time this inflates every call against the token budget — worth measuring again once the real evaluator endpoint is known.
- **B. Persona bleed:** 2 of 5 replies identified as "I'm Kiro, your AI-powered development environment" instead of the harness role — the upstream proxy partially overrides the harness's system prompt. 3 of 5 roles held correctly. If this persists on the evaluator's endpoint, mitigation is to put critical role instructions in the first user turn rather than (only) the system message.
- **C. Model-name drift:** user requested "claude-sonet-5"; gateway serves `claude-sonnet-4.5` as the newest Sonnet. Config-only change if the evaluator prescribes a different ID.

## Artifacts

- Sweep config: `/tmp/harness-review/harness.yaml` (temp, outside repo)
- Sweep script: `/tmp/harness-review/test_agents.py` (per-agent ping + tool round-trip; reusable for any future endpoint: `AI_API_KEY=<key> .venv/bin/python test_agents.py <repo-root> <config-dir>`)
- Related reports: [Milestone 1 review](2026-09-26-milestone1-foundation-review.md) · [Milestone 2 review](2026-09-26-milestone2-agents-review.md)
