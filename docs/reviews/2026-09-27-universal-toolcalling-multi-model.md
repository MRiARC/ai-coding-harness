# Universal Tool-Calling + Multi-Model Live Verification (M5 hardening, improvements §3.1)

**Date:** 2026-09-27 · **Branch:** `feat/universal-toolcalling` · **Scope:** the audit's §3.1 "our harness didn't run" risk — never assume the model's calling convention.

**Trigger:** the organizers' test models were identified (**DeepSeek and Qwen families**) — and the local gateway turned out to serve them all: `deepseek-3.2`, `qwen3-coder-next`, `glm-5`, `minimax-m2.5` alongside the Claude family.

## What was built

| Piece | Detail |
|---|---|
| **Capability probe** | One cheap round-trip detects native tool calling per model; cached per (provider, model, base_url); probe failure is optimistic (native), matching pre-probe behavior |
| **Text-protocol fallback** | For tool-call-less models: tool manual rendered into the system prompt, `TOOL_CALL: {json}` directives parsed (fence/malformed tolerant), results returned as user turns so the wire stays valid |
| **Reasoning-model tolerance** | `<think>` blocks stripped from content (Qwen-style), `None` content handled (DeepSeek-R1-style `reasoning_content`) |
| **Config** | `ModelConfig.tool_call_mode: auto (probe) \| native \| text` |
| **Live findings folded back in** | Free-form plan specialties (`bugfix`) route by role, not luck (fixed in M4 wrap-up); tool-name aliases from the teammate's parallel work |

## Probe results (gateway, 2026-09-27)

| Model | Native tool calls | Notes |
|---|---|---|
| deepseek-3.2 | ✅ (finish=tool_calls, ids `tooluse_…`) | |
| qwen3-coder-next | ✅ | no `<think>` leakage in normal mode |
| glm-5 | ✅ | |
| minimax-m2.5 | ✅ | behavior gap found live — see below |
| claude-sonnet-4.5 | ✅ | (M4 baseline) |

## Live end-to-end results (`harness solve`, fixture issue, exit codes)

| Model | Result | Notes |
|---|---|---|
| claude-sonnet-4.5 | ✅ **VERIFIED, exit 0** | M4's proof run |
| deepseek-3.2 | ✅ **VERIFIED, exit 0** | probe detected native mid-run; 4 tool turns; all gates green |
| qwen3-coder-next | ✅ **VERIFIED, exit 0** | same; patch verified correct (`a - b` → `a + b`) |
| glm-5 | ✅ **VERIFIED, exit 0** | |
| minimax-m2.5 | ❌ **NOT VERIFIED, exit 1** | **model claimed the edit without calling the tool** ("Fixed… all tests pass" + TASK_COMPLETE, empty diff) — the integrity/test gates caught the hallucination and failed the run honestly |

## The minimax finding — the system working as designed

The failure mode the audit's §6 warned about materialized live: a model *asserted* success instead of acting. The pipeline refused to bless it — empty diff, `reproduction test still failing`, exit 1 with an honest `summary.md`. **Four of five model families fully verified; the fifth was caught, not silently wrong.**

**Follow-up idea (candidate for the next hardening round):** when verification fails with "reproduction still failing" and the task summary *claims* success, feed the verification failure back through the recovery ladder once (bounded) before giving up — converting minimax's run from honest-fail into a likely verified pass on attempt 2. Deliberately not built in this round: it changes run-level semantics and deserves its own tests.

## Verification

- Offline: full suite green, **100% enforced coverage**, ruff + strict mypy clean, CI on Python 3.11/3.12
- New tests: probe (native/text/optimistic-failure/cache), text-protocol loop (tool manual rendered, `tools: null` on the wire, results as user turns, alias + marker semantics), think-strip, config round-trip
