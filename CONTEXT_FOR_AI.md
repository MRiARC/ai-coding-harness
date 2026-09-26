# AI Context — Read This First

**Project:** LCC x DevClub AI Coding Harness ("Foreman") — an autonomous
coding-agent harness for the hackathon's evaluation.

## Source of truth (in order)

1. **`docs/specs/foreman-eval-mode-design.md`** — the approved design. The
   runtime architecture, evaluation contract, and build order live here.
2. **The code in `src/harness/`** — if code and an older document disagree,
   the code wins and the document is stale.
3. **GitHub issues** — the current work plan (Milestones 1–4).

## What this project IS

A single-process Python harness (3.11+) that turns **one prescribed model**
(supplied by the organizers via `AI_API_KEY` at eval time) into a software
engineer on a target repository + issue:

```
issue text → Architect (plan) → Manager (routing, overlap gate, budget,
recovery) → Locator/Implementer/Verifier loops over ~12 tools →
verification pipeline → evidence pack (patch, trace.jsonl, test report,
baseline, token report, summary)
```

- Interface contract: `export AI_API_KEY=… && make setup && make run`
  (issue supplied as text: `--issue`, `--issue-file`, env var, or stdin).
- Offline-first: no GitHub credentials, no network beyond the model API,
  SQLite context store, fake provider for offline tests.
- Exit codes: 0 verified · 1 unverified changes · 2 failed · 3 budget exhausted.

## What this project is NOT (legacy vision docs — do not implement against)

`DESIGN_SPEC.md` and `TECHNICAL_IMPLEMENTATION.md` describe the original
**long-term vision**: a multi-service platform (Go API gateway, Python
LangGraph service, React dashboard, PostgreSQL, Redis, GitHub PR flows).
Those runtime assumptions were **superseded** by the Foreman design — the
evaluation environment has none of that infrastructure. Read them for
concepts (verification stages, escalation levels, assignment weights) that
survived, never as build instructions. Same for the old issue backlog
(#4–#41 sub-issues that mention Go/React/specialist zoos).

## Key modules

| Path | Role |
|---|---|
| `src/harness/agents/` | LLMAgent loop, Architect (plan/review), Manager (routing/overlap/recovery), role presets |
| `src/harness/engine/` | Pipeline orchestration, budget governor, recovery ladder, evidence packs |
| `src/harness/tools/` | 12-tool registry (read/search/edit/test/git/execution/scan) |
| `src/harness/verification/` | Integrity gate, syntax check, baseline + regression judgment, AST smells, secret scan |
| `src/harness/infrastructure/` | Model providers (openai/anthropic/google/openai-compatible/fake), context store, git, GitHub (optional) |
| `src/harness/monitoring/` | Metrics + health checks |
| `src/harness/security/` | Input guards, secret scanner, hash-chained audit log |

## Conventions

- Tests: pytest with **enforced 100% statement coverage** (`fail_under=100`),
  strict mypy, ruff. CI runs Python 3.11 and 3.12 — local green is not enough.
- Credentials only ever enter via environment variables (`api_key_env`
  indirection); never commit keys or write them into config files.
- Git: PRs target `main` directly (no stacked feature-branch bases); one
  commit per sub-issue keeps review history readable.
