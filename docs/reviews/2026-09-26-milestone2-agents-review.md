# Milestone 2 (Agent System & Orchestration) — Review Report

**PR reviewed:** #44 "Milestone 2: Agent System & Orchestration (issues 2.1–2.13)" (`feat/agents`, single commit `61af785`)
**Reviewed / landed:** 2026-09-26 by automated review (ZCode) on behalf of the repo owner
**Verdict:** ✅ **Approved and merged into `main`** (`9fdd778`)

> Base-branch note: PR #44 was opened with base `feat/foundation` (stacked), so
> `gh pr merge` landed it on `feat/foundation` (commit `c692a8a`) rather than
> main. This review merged `feat/foundation` → `main` directly (CI had already
> validated the exact tree). Future stacked PRs: set base `main`, or merge
> bottom-up via the UI.

---

## 1. What was verified

| Check | Result |
|---|---|
| Offline test suite | ✅ **199 passed** (up from 123), 100% coverage enforced on 1,513 statements |
| Lint (`ruff check` + format) | ✅ clean, 53 files |
| Type check (`mypy` strict) | ✅ no issues in 32 source files |
| CI (Python 3.11 + 3.12) | ✅ all SUCCESS on the PR |
| Manual code review | ✅ all new modules read in full (see §2) |

## 2. What landed (~1,260 src lines + ~1,100 test lines)

| Module | Contents |
|---|---|
| `agents/llm_agent.py` | The concrete agent loop: budget check per step, tool calls validated + permission-gated with failures returned as tool *results* (never exceptions — recovery can reason over them), automatic context compression past `keep_recent`, JSON extraction (fenced/balanced-brace) with one repair round for structured calls |
| `agents/architect.py` | `analyze_repository` → `RepositoryProfile`, `decompose` → `Plan` (subtasks with acceptance criteria, files, deps), `review` → `ReviewVerdict`, `reframe` (L3 recovery). All structured-JSON calls, persisted to global context |
| `agents/manager.py` | DESIGN_SPEC §5.1 assignment algorithm **verbatim as pure functions** (40/20/20/20 weights), pairwise file-overlap detection, `execution_batches` (disjoint file-sets ⇒ parallelizable batches — the escalation gate), escalation categorization, LLM-assisted reframing |
| `agents/prompts.py` | 13 role presets (eval trio + classic specialists) with specialties + max tool tiers; system-prompt composer injects the fact ledger |
| `agents/specialists.py` | Specialty→role mapping + `build_agent` factory |
| `engine/budget.py` | Budget governor: NORMAL / SURGICAL (70%) / FINALIZE (90%) / `BudgetExhausted` at 100%, metered via the context-store ledger |
| `engine/recovery.py` | Recovery ladder L1 self-repair ×3 → L2 re-route ×2 → L3 re-plan ×1 → L4 graceful give-up (honest `TaskResult`, never a hang) |
| `agents/base.py`, `task.py`, `config.py` | Contracts made async; `Task` gained specialty/complexity/required_tools/files (overlap-gate inputs); config role registry widened to all 13 roles |

Faithfulness to the design docs is high: the adversarial-Verifier rule
("you never see the implementer's reasoning") is in the Verifier's system
prompt; the "never weaken assertions / never touch tests unless told" rules
are in the Implementer/Testing prompts; recovery/budget parameters match the
Foreman spec exactly.

## 3. Minor notes (non-blocking)

1. `manager.specialty_match()` accepts a `performance` parameter that is
   currently unused (docstring says "scaled by historical success"). Either
   wire it in or drop the parameter.
2. `FINAL_MARKER` (`TASK_COMPLETE:`) is advertised in the loop prompt but not
   enforced by `_loop` — any bare reply ends the loop. Pragmatic; consider
   enforcing the marker in a later milestone so specialists can't "finish"
   by chatting.
3. The filesystem indexer / tool runtime (tree-sitter, BM25, `apply_edit`,
   `run_tests`) is still pending — the agents run against an empty tool
   registry until Milestone 3 lands. Expected per the build order.

## 4. Live-model verification

Separate from this review, the user-supplied API key (believed to be Anthropic
`claude-sonnet-5`) was probed: it is rejected by **both** `api.openai.com` (401)
and `api.anthropic.com` (`authentication_error: invalid x-api-key`), so it is
gateway-issued — pending the gateway `base_url` from the organizers'
announcement. The 5-agent live sweep is fully prepared (temp harness + script,
dry-run validated end-to-end); the provider transport itself is unit-tested
with mocked HTTP, so this does not gate the merge.
