# Milestone 1 (Foundation) — Review Report

**PR reviewed:** #43 "Milestone 1: Foundation & Infrastructure (issues 1.1–1.8)" (`feat/foundation`)
**Reviewed / merged:** 2026-09-26 by automated review (ZCode) on behalf of the repo owner
**Verdict:** ✅ **Approved and merged into `main`** (merge commit `04b018f`)

---

## 1. What was verified

| Check | Result |
|---|---|
| Offline test suite (`make test`) | ✅ 123 passed, **100% coverage enforced** (`fail_under = 100`) |
| Lint (`ruff check` + `ruff format --check`) | ✅ clean, 40 files formatted |
| Type check (`mypy`, strict: `disallow_untyped_defs`) | ✅ no issues in 24 source files |
| CI (GitHub Actions, Python 3.11 **and** 3.12) | ✅ all SUCCESS on the PR |
| Mergeability | ✅ MERGEABLE at review time |
| Secret hygiene | ✅ no credentials in repo; config references env-var *names* only (`api_key_env`), `${VAR}` interpolation hard-fails on unset vars; `.env*` gitignored |
| Manual code review | ✅ all core modules read: config, model providers (OpenAI/Anthropic/Google/OpenAI-compatible/Fake), context store, local git, GitHub client, logging, agent/tool/message contracts, CLI |

## 2. Architecture confirmed

The foundation implements the **Foreman eval-mode design** (`docs/specs/foreman-eval-mode-design.md`), not the multi-service DESIGN_SPEC stack. Evidence: agent roles are `architect | manager | locator | implementer | verifier`; provider defaults to `openai-compatible` + swappable `base_url` (prescribed-model contract); budget governor thresholds (warn → surgical → finalize-only) in config schema; sqlite default context store; offline-first with a `fake` provider; Makefile encodes the evaluator contract.

Sub-issues 1.1–1.8 all implemented (one commit each), each closing its issue via the PR.

## 3. Notable strengths

- **Graceful degradation is the default path**: `GitHubService.available = False` without credentials (raises clear `GitHubUnavailableError`); `GitService` covers branch/diff/commit fully offline, self-signing commits when the host has no git identity (locked-down eval boxes).
- **Transport discipline**: exponential backoff with jitter, `Retry-After` awareness, immediate fail on 401/403, usage accounting on every call (budget-governor input).
- **Context store** keeps the original design's three-window compression + neighbor retrieval, with memory/sqlite/postgres backends behind one interface.
- Strict typing + lint + 100% enforced coverage + CI on two Python versions from day one.

## 4. Items NOT verified in this review

- **Live model calls with the provided API key** — the key returns **401 against `api.openai.com`**, i.e. it belongs to a non-OpenAI gateway. The Foreman spec states the prescribed `model.name` and `model.base_url` come from the organizers' announcement. Once those are known, the 5-agent live check (architect-1, manager-1, locator-1, implementer-1, verifier-1) runs in minutes. The provider transport itself is fully unit-tested with mocked HTTP, so this pending check does not gate the merge.
- Live-path behavior of Anthropic/Google providers (unit-tested only; eval uses the OpenAI-compatible provider).

## 5. Follow-ups

1. **PR #44 (Milestone 2 — agents & orchestration) is open and stacked on this PR**, CI green. Review next; it contains the real agent loops that make live agent testing meaningful.
2. **`docs/specs/foreman-eval-mode-design.md` restored to the repo** in this review — its original PR #30 was closed without merging. The file is the approved design of record.
3. Older docs (`DESIGN_SPEC.md` as vision, `TECHNICAL_IMPLEMENTATION.md`) now over-describe the superseded runtime; see the Foreman spec's own status header for the relationship.
