# Milestone 4 — Hardening & Live Proof (Review + Verification Report)

**Scope:** issues #46 (epic) + #47–#58, driven by the independent adversarial audit (`docs/audits/2026-09-26-adversarial-audit.md`)
**Implemented / verified:** 2026-09-26 by ZCode (on behalf of the repo owner)
**Verdict:** ✅ **All 12 sub-issues implemented; the audit's minimum bar is met — the harness solved a real issue end-to-end against the live model gateway (exit 0, VERIFIED).**

---

## 1. Offline verification

| Check | Result |
|---|---|
| Test suite | ✅ 350+ passed, **100% coverage enforced** on 3,200+ statements (up from 329/3,072) |
| Lint + strict mypy | ✅ clean |
| CI | ✅ Python 3.11 + 3.12 (PR run) |
| Demo gate (#57) | ✅ 3 seeded fixture scenarios through the real pipeline: VERIFIED run, test-edit cheat **rejected**, recovery demonstrated |

## 2. What landed (one area per audit finding)

| Audit § | Fix | Where |
|---|---|---|
| §5 (release-blocking) | **Structured tool-call conversation state**: assistant `tool_calls` + paired `tool_call_id`s preserved through store → window → wire; strict-provider payloads validated by mocked-HTTP OpenAI *and* Anthropic round-trip tests | `context_store.py` (schema v2), `llm_agent.py`, all providers |
| §10 | **Context window rebound per task execution**; task text guaranteed in first model call | `llm_agent.execute_task` |
| §9 | **Task fields reach the model**: acceptance criteria, expected files, required tools, manager guidance (capped) | `compose_task_prompt` |
| §8 | **Recovery evidence injected** into retries; L2 `reassign` genuinely swaps specialists; `add collaborators` spawns a bounded real collaborator (autoscaling wiring); ladder transitions traced | `recovery.py`, `pipeline.py` |
| §22 | **Awaitable subprocess tools** (`execute_async` via `create_subprocess_exec`); parallel batches no longer serialize on 60s test runs; concurrency test proves overlap | `tools/base+execution`, `verification/pipeline` |
| §11 | **Dependency-safe batching**: `depends_on` gates batch entry; unknown/empty file-sets run solo; cycles degrade to sequential | `manager.execution_batches` |
| §13 | **Budget modes govern**: SURGICAL/FINALIZE directives in prompts, L3 re-plans suppressed outside NORMAL, `reserve()` blocks overshooting dispatches | `budget.py`, `llm_agent`, `recovery` |
| §20 | **Chunked evidence-fed review**: per-file chunks, overflow files named and gate failed honestly; verification evidence in the review prompt | `architect.review` |
| §15/16/17 | **Honesty pass**: `postgres` backend rejected at validation; runtime deps pinned exactly; `CONTEXT_FOR_AI.md` rewritten as source-of-truth pointer; README hierarchy block | `config.py`, `pyproject.toml`, docs |
| §24/27/28 | **Demo gate**: `fixtures/mini-repo` + seeded issues; behavioral end-to-end tests in CI | `tests/integration/test_demo_gate.py` |
| §1.1/1.3 | **Reproduction-first baseline**: pre-patch suite run, `baseline.json` in the pack, reproduction must flip fail→pass, pre-existing failures exempt; **test-integrity gate** blocks test-file edits without plan allowance; honest degradation when the suite is unrunnable | `verification/baseline+integrity`, pipeline stages 1/3 |

Plus one **live-run discovery**: the Architect emits free-form specialties (`bugfix`) that matched no slot, so the fix task tied at neutral score and landed on the read-only Locator. Fixed with role-aware routing (`SPECIALTY_ROLES` synonyms + slot `role` matching) — regression-tested.

## 3. Live end-to-end proof (#58) — the audit's minimum bar

`harness solve --repo <mini-repo copy> --issue-file fixtures/issues/issue-add.md`
against the local prescribed-model gateway (`claude-sonnet-4.5` via OpenAI-compatible protocol).

**Run 1** (pre-routing-fix): the pipeline ran fully live — architect analyzed + planned 4 subtasks, specialists worked multi-turn — and ended **honestly NOT VERIFIED (exit 1)** because the fix task had been routed to the Locator. The verification pipeline caught it: `reproduction test still failing`. This is the failure mode the audit warned about, being caught by the machinery built in this milestone.

**Run 2** (post-fix): **VERIFIED, exit 0.**

| Evidence | Value |
|---|---|
| Reproduction | `test_calculator.py::test_add` — `reproduction_failing_before: true` → passes after |
| Baseline | 3 pre-existing failures recorded; all exempt from regression blame |
| Patch | exactly one line: `return a - b` → `return a + b` |
| Gates | 1-integrity ✅ · 2-self-check ✅ · 3-local-tests ✅ (no regressions; repro passes) · 4-code-review ✅ (2 advisories) · 5-security ✅ · 6-final-review ✅ ("All acceptance criteria met… single-line change") |
| Multi-turn native tool calls | 7+ consecutive tool-calling turns against the live gateway (validates §5 fix on real wire) |
| Tokens | architect ≈24.7k, implementer ≈71.2k (incl. ~4.4k/call gateway-injected system prompt — the known overhead), verifier similar; budget governor stayed NORMAL |

Artifacts: `/tmp/m4-live/repo/results/09decdff84bf/` (patch.diff, baseline.json, test-report.md, token-report.json, summary.md, trace.jsonl).

## 4. Remaining known gaps (honest)

1. **Gateway prompt-injection overhead**: ~4.4k tokens/call injected by the proxy; at eval time this consumes budget — measure against the official endpoint.
2. **Persona bleed**: the gateway's upstream persona still occasionally leaks into replies (2/5 in the earlier sweep).
3. Verifier/architect-as-LLM stages are advisory on top of the deterministic gates — by design for eval mode.
4. `1-integrity` treats any `tests/`-path edit as a violation without allowlist — correct default, may need per-repo nuance later.

## 5. Verdict against the audit's bottom line

The audit's label — *"foundation and orchestration framework, not an autonomous coding harness"* — is now **falsified by execution**: clean clone → `make setup` → `make run` (issue via file) → correct patch → reproduction fail→pass → all gates green → evidence pack → exit 0, live. The remaining work is polish (overhead, personas), not existence.
