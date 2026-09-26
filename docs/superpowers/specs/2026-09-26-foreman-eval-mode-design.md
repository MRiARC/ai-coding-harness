# Foreman — Eval-Mode Design Specification

**Project:** LCC × DevClub AI Coding Harness Hackathon 2026
**Repo:** `ai-coding-harness`
**Status:** Approved design (2026-09-26). Supersedes the runtime assumptions of `DESIGN_SPEC.md`, which remains the long-term vision document.
**Stack:** Python 3.11+ · Team timeline: 1–2 weeks

---

## 1. Purpose

Build an autonomous coding-agent harness that turns one prescribed, text-only foundation model into a capable software engineer on a given repository + issue. The hackathon scores three axes — **correctness first, evidence over claims, efficiency matters** — under a fixed evaluation contract:

```
git clone <repo> && cd <repo>
export AI_API_KEY="<PROVIDED_API_KEY>"
make setup
make run          # launches the harness in its intended evaluation mode
<issue text>      # supplied by evaluator per official procedure
```

Foreman's identity: a **hierarchical agent org** (Architect → Manager → Specialists) with an **escalation-gated** execution strategy — sequential by default, parallel only when measurement says parallelism is safe.

### Non-goals (explicitly out of scope for eval mode)

- GitHub push/PR/CI integration (no credentials in the eval environment)
- PostgreSQL, Docker, Slack/email notifications, web dashboard
- Multi-provider model tiers / dynamic model selection (one prescribed model)
- Image/audio/video input of any kind (text-only by construction)
- Plugin system, distributed tracing, 10 specialist personas

---

## 2. Evaluation-constraint compliance

| Constraint | How Foreman complies |
|---|---|
| `AI_API_KEY` env var | Read at startup, never logged, never written to disk. Config uses `api_key_env: AI_API_KEY`. Startup fails fast with a clear message if unset. |
| Text-only model | All model calls are text chat completions; no multimodal code paths exist. |
| Prescribed model | `harness.yaml` pins `model.name` and `model.base_url`; changing providers touches config only, never source. Organizers' announcement slots into config. |
| Makefile contract | `make setup` / `run` / `test` / `clean` at repo root (Section 8). |
| Issue as text | Four intake paths (Section 7) cover paste, file, stdin, env var. |
| Reproducible execution | Temperature 0, pinned dependency versions, FakeModel determinism, seeded fixtures. |
| Unattended evaluation | No human-escalation level; recovery ends in graceful, documented failure with exit code (Section 6). |

---

## 3. Architecture

Five layers; the hierarchy from `DESIGN_SPEC.md` survives with eval-mode scope:

```
L1  Interface        TUI cockpit (Textual)  ·  headless runner  →  same engine
L2  Orchestration    ARCHITECT   (1 LLM agent)   plan · acceptance criteria · final review
L3  Coordination     MANAGER     (code + small LLM calls)  routing · overlap gate · budget · recovery
L4  Execution        LOCATOR · IMPLEMENTER · VERIFIER   (role-prompted agent loops)
L5  Infrastructure   tool runtime (~10) · model client · JSONL event store · local git · subprocess sandbox
```

- **Architect** (LLM): consumes issue + repo-map; produces a plan of subtasks, each with acceptance criteria and risk notes; performs the final review of the aggregate diff against acceptance criteria.
- **Manager** (mostly deterministic code, LLM only where judgment is needed): routes subtasks to specialists, computes the file-overlap gate, enforces the budget governor, drives the recovery ladder, owns integration checks.
- **Specialists**: three fixed roles, each a standard agent loop over the shared tool runtime with a role system prompt:
  - **Locator** — pins the files, symbols, and line ranges relevant to a subtask using search tools; emits a localization artifact consumed by the overlap gate.
  - **Implementer** — writes the change: reads localized context, produces unified diffs via `apply_edit`.
  - **Verifier** — runs the relevant tests, reviews the diff for correctness and regressions, returns a verdict with evidence.

### 3.1 Escalation-gated parallelism (the overlap gate)

After the Architect's plan, the Manager computes the intersection of subtask file-sets **from Locator artifacts** (static, no LLM cost):

- Subtask file-sets **disjoint** → those subtasks run as parallel specialists in separate `git worktree`s; Manager merges sequentially and runs the full test suite after each merge.
- **Overlapping** → sequential pipeline in one working tree (default).
- Tie-breaker: if parallelism saves an estimated <30% wall-clock (estimated from subtask step counts), stay sequential — coordination overhead is not free.

This gate degrades to pure sequential (Approach A) by disabling one config flag; nothing else changes.

---

## 4. Runtime flow (one eval issue)

1. **Bootstrap — zero LLM tokens.** Index the target repo: tree-sitter symbol extraction, BM25 index (`bm25s`), gitignore-aware file tree, build-system and test-runner detection (Makefile / pyproject.toml / package.json / setup.py → test command), compact aider-style repo-map. All of this is deterministic Python.
2. **Issue intake** (Section 7) → normalized task object.
3. **Architect** plans: subtasks + acceptance criteria + risks (one structured call, JSON output).
4. **Manager** runs the overlap gate → execution order / worktree fan-out.
5. **Per subtask:** Locator → Implementer → Verifier. Verifier's failing test output is *evidence*, feeding recovery directly.
6. **Recovery ladder** (attempt-budgeted, per Section 6).
7. **Architect final review:** aggregate diff vs acceptance criteria → verdict + written rationale.
8. **Evidence pack** written to `results/<run-id>/`:
   - `patch.diff` — final unified diff
   - `trace.jsonl` — every event: prompts (hashed), tool calls + results, model usage per call, decisions
   - `test-report.md` — commands run, per-test outcomes
   - `token-report.json` — spend per agent/tool/phase vs budget
   - `summary.md` — human-readable narrative of what was done and why
   - Process exit code: `0` verified, `1` unverified changes, `2` failed, `3` budget exhausted.

---

## 5. Efficiency mechanisms (scored differentiators)

1. **Localization-before-LLM:** symbol graph + BM25 + ripgrep narrow the context *before* any model call, so the Architect and Implementer read hundreds of relevant lines instead of thousands of irrelevant ones.
2. **Budget governor:** Manager meters every model call against a global token budget (`budget.total_tokens`, default 2M). Thresholds:
   - 70% → **surgical mode**: no re-plans, exploration tools rate-limited, Implementer works from existing localization only.
   - 90% → **finalize-only**: Verifier runs, Implementer may fix only verified-failing tests, then stop.
   - 100% → stop, emit evidence pack, exit 3.
   The current meter is exposed to agents via `token_meter` so the model itself can budget.
3. **Two-tier context:** full-fidelity recent window (last `context.recent_window` messages per agent, default 40) + rolling compressed summary + a structured **fact ledger** (decisions, file insights, dead-ends) injected into every agent's system context. Repo-map built once per plan phase, not per step.

---

## 6. Recovery ladder (unattended variant of the 4-level hierarchy)

| Level | Actor | Trigger | Action | Budget |
|---|---|---|---|---|
| L1 Self-repair | Same specialist | Verifier failure / tool error / malformed output | Error + evidence fed back to the same specialist | 3 attempts |
| L2 Re-route | Manager | L1 exhausted | Change strategy: different file interpretation, narrower edit, re-run Locator with refined query, or reassign role | 2 attempts |
| L3 Re-plan | Architect | L2 exhausted | Re-decompose the subtask; may drop to a smaller-scope interpretation of the acceptance criteria | 1 attempt |
| L4 Give-up, gracefully | Manager | L3 exhausted or budget governor forces stop | Emit best-effort diff + honest failure report in `summary.md`; exit code reflects state | — |

A hang is worse than a documented failure: every model call has a timeout; every command has a timeout; the whole run has a wall-clock cap (`limits.wall_clock_seconds`, default 1800).

---

## 7. Issue intake

The task arrives as text. Foreman accepts, in priority order:

1. TUI paste (interactive eval)
2. `--issue-file <path>` CLI flag
3. stdin pipe (`cat issue.md | make run` or piped launcher)
4. `HARNESS_ISSUE` / `HARNESS_ISSUE_FILE` environment variables

All paths normalize to one `Task` object (title, body, raw text). Whatever protocol the organizers use, no source changes are needed.

---

## 8. Makefile contract

| Target | Behavior |
|---|---|
| `make setup` | `python3 -m venv .venv` + `.venv/bin/pip install -U pip` + `pip install -e .` from `pyproject.toml` (pinned). No network beyond PyPI. Verifies Python ≥3.11 and `AI_API_KEY` presence (warn-only for `test`). |
| `make run` | `.venv/bin/python -m harness.cli run`. Launches TUI; auto-falls back to headless when no TTY. Reads `AI_API_KEY` from environment. |
| `make test` | Offline pytest suite + fixture eval on `fixtures/mini-repo` (3 seeded issues). Without `AI_API_KEY`: FakeModel replay — fully offline. With key: optional live eval marker runs against the real model and prints pass-rate + tokens-per-task. |
| `make clean` | Removes `results/`, `__pycache__`, `.pytest_cache`, `.harness/` (worktrees). Keeps `.venv`. |

---

## 9. Component details

### 9.1 Tool runtime (~10 tools, shared)

| Tool | Purpose | Notes |
|---|---|---|
| `read_file` | Range reads with line numbers | Truncation-aware |
| `list_dir` | Directory listing | Gitignore-aware |
| `search_text` | Ripgrep wrapper | Primary workhorse |
| `search_symbols` | Tree-sitter symbol queries | Definitions + references |
| `repo_map` | Compact codebase map | Precomputed at bootstrap |
| `apply_edit` | Unified-diff apply | Validates context lines; precise errors feed recovery |
| `run_tests` | Detected test runner | Timeout, truncated output, per-test results |
| `run_cmd` | Sandboxed command | Timeout + project-dir confinement + full logging |
| `git_local` | status / diff / branch / worktree | Local only; push is not implemented |
| `token_meter` | Live spend vs budget | Visible to agents and TUI |

Every tool call is validated (paths confined to the repo, no shell metacharacter injection into `run_cmd`'s allowlisted commands) and logged to `trace.jsonl`.

### 9.2 Model client

Thin `httpx` client against the OpenAI-compatible Chat Completions API. Features: exponential-backoff retries (max 3), per-call timeout, usage accounting from response payloads, structured JSON-output helper for Architect/Manager calls. `FakeModel` replays recorded responses (determinism + offline testing). Key sourced only from `AI_API_KEY`.

### 9.3 TUI cockpit (Textual)

Panes: **Plan** (subtask tree + status) · **Activity** (live event stream per agent) · **Diff** (current changes) · **Tests** (last verdict) · **Tokens** (budget bar). Actions: paste issue, run, pause, export evidence. The TUI is a *view* over the event store — the engine never depends on it (headless parity).

### 9.4 Evidence pack

One directory per run under `results/<run-id>/` (Section 4, step 8). `trace.jsonl` is the audit spine: judges (and our own debugging) can replay the entire decision chain.

---

## 10. Testing strategy

- **Unit:** tools (edit-apply edge cases, path confinement), overlap gate, budget governor thresholds, context compression, issue-intake normalization.
- **Integration:** full pipeline on `fixtures/mini-repo` with FakeModel — 3 seeded issues (one easy, one needing multi-file edit, one recovery scenario).
- **Live (optional):** pytest marker `live` runs the same fixtures against the real model when `AI_API_KEY` is set; reports pass-rate and tokens-per-task.
- **Clean-room check before submission:** fresh clone → `make setup && make run` with a dummy key and a fixture issue; documented in the README.

---

## 11. Repository layout

```
Makefile · pyproject.toml · README.md · harness.yaml
harness/
  agents/    base · architect · manager · locator · implementer · verifier
  engine/    loop · events · budget · context
  tools/     (one module per tool + registry)
  models/    client · usage · fake
  indexing/  repomap · symbols · bm25 · detect (build/test detection)
  tui/       app · panes/
  cli/       run
configs/     harness.yaml (defaults; root copy is the live config)
fixtures/    mini-repo/ · issues/ · recorded/
results/     (gitignored)
docs/        DESIGN_SPEC.md (vision) · this spec · eval-mode addendum
tests/       unit/ · integration/
```

---

## 12. Dependencies (builds on — cited in README)

| Dependency | Role | License |
|---|---|---|
| `tree-sitter` + `tree-sitter-languages` | Symbol extraction / repo-map | MIT |
| `bm25s` | Fast BM25 lexical search | MIT |
| `ripgrep` (subprocess, vendored or system) | Text search | MIT/Apache-2.0 |
| `textual` | TUI cockpit | MIT |
| `httpx` | Model API client | BSD-3 |
| `pydantic` | Config + structured outputs | MIT |
| `tiktoken` (or response usage fields) | Token accounting | MIT |

**Studied / adapted with attribution:** `aider`'s tree-sitter repo-map approach (Apache-2.0), `moatless-tools` and `Agentless` (localization strategy references). These are cited as researched foundations — a deliberate "we build on the best obscure work" story.

---

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Unknown eval issue-delivery protocol | Four intake paths (Section 7) |
| Unknown prescribed model/endpoint | Config-only switch; OpenAI-compatible is the common denominator |
| Hierarchy overhead burns tokens | Overlap gate defaults to sequential; budget governor caps damage; single-call planning |
| Parallel worktrees introduce merge pain | Only fan out on measured disjoint file-sets; full suite after each merge |
| TUI breaks on evaluator's terminal | Auto-headless fallback; engine never depends on TUI |
| Tree-sitter parse failures on odd languages | BM25 + ripgrep still work; repo-map degrades gracefully |
| Model returns malformed JSON/edits | One repair prompt, then treat as L1 failure evidence |

---

## 14. Build order (1–2 weeks)

1. **Skeleton + Makefile + model client + FakeModel** (day 1–2) — the graded interface works first.
2. **Tool runtime + indexing** (day 2–4) — repo-map, BM25, search, apply_edit, run_tests.
3. **Single-loop pipeline** (day 4–6) — Architect → Locator → Implementer → Verifier sequential, evidence pack, headless.
4. **Manager: overlap gate + recovery ladder + budget governor** (day 6–8).
5. **TUI cockpit** (day 8–10).
6. **Fixtures, live-eval polish, clean-room run, docs** (day 10–12). Buffer: 2 days.

Each stage leaves the repo in a state where `make setup && make run` works.
