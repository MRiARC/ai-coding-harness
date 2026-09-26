# Foreman — Improvement & Optimization Roadmap

> Companion roadmap to the Foreman eval-mode design. Ordered by the hackathon's scoring axes:
> **correctness first, evidence over claims, efficiency matters.**
> Each item states what it is, why it scores, and how it is implemented.

---


---

## 0. Implementation status (2026-09-27)

> Living scorecard — updated as items land. References point to the commits/PRs
> that implemented each item. ✅ done · 🟡 partial · ❌ open (see linked issue).

| # | Item | Status | Where |
|---|---|---|---|
| 1.1 | Reproduction-first verification & baseline gating | ✅ | `6f4b364` (M4.10, #53) |
| 1.2 | Search/replace edit format + syntax gate | ✅ | M3 `apply_edit` + `syntax_check` |
| 1.3 | Test-integrity guard & diff minimality | ✅ | `6f4b364` (M4.10, #53) |
| 1.4 | Isolated adversarial Verifier | 🟡 | isolation is prompt-level (M2); no enforced verdict protocol — deterministic gates (M3/M4) carry correctness |
| 1.5 | Environment probe & baseline runnability | ✅ | M3 health checks + runner detection |
| 2.1 | Complexity triage / fast path | 🟡 | complexity drives collaboration threshold + batch sizing; single-agent fast path below threshold not built |
| 2.2 | Observation compression | ✅ | `69c9bae` (M5.2, #61 — stale tool-result stubs) |
| 2.3 | Regression test selection | 🟡 | `run_tests` path subset; full import-graph selection open |
| 2.4 | Prompt-prefix stability | 🟡 | structural (system prefix byte-stable); formal caching = #65 |
| 2.5 | Index cache keyed by commit | 🟡 | `.harness/` caches exist; commit-keyed store open |
| 2.6 | Personalized PageRank repo-map | ❌ | tracked with #60 (context graph) |
| 3.1 | Model-capability probe + dual calling modes | ✅ | `doctor --probe-model` + universal tool-calling (`a6e437c`) |
| 3.2 | Loop detector & dead-end ledger | ✅ | `69c9bae` (M5.3, #62 — dedup strikes + bounded nudges) |
| 3.3 | Rate limiter | 🟡 | transport retry/backoff + `governor.reserve()` (token budget) exist; 429-aware concurrency limiter across parallel specialists open |
| 4.1 | Trace replay + `make report` | 🟡 | `harness replay` shipped; HTML report open |
| 4.2 | SWE-bench Lite localization-recall | ❌ | #66 |
| 4.3 | Best-of-N gated fallback | ❌ | not scheduled |
| — | Platform layer (Go gateway, Redis, Go TUI) | 🟡 | epic #69 (P1–P3 in flight, #70–#75) |

---


## 1. Correctness improvements

### 1.1 Reproduction-first verification & baseline gating
**What:** Before any edit, run the target repo's test suite once and record the *baseline* — which tests already fail on unmodified code. The Locator/Implementer then produce (or identify) a **reproduction test** that fails on unmodified code and encodes the issue. Done means: reproduction test flips to pass **and** the baseline-passing set stays green.
**Why:** Prevents blaming pre-existing failures on our patch; produces a literal fail→pass proof in the evidence pack — the strongest possible "evidence over claims" artifact. Most teams skip this entirely.
**How:** Bootstrap stage runs the detected test runner once; baseline stored in the run state; Verifier diffs current results against baseline; reproduction test recorded in `test-report.md`.

### 1.2 Search/replace edit format with syntax gate
**What:** Make search/replace blocks (aider-style) the primary edit format instead of unified diffs; fuzzy-whitespace matching as fallback; whole-file rewrite allowed for files under ~50 lines. After every applied edit, run a **syntax check** (tree-sitter parse or `py_compile`) before any test run.
**Why:** LLM-generated unified diffs fail to apply constantly (line drift, context mismatch). Search/replace is measurably more reliable across models. The syntax gate catches broken edits for near-zero tokens.
**How:** `apply_edit` accepts both formats; parser-based validation returns precise errors that feed the recovery ladder.

### 1.3 Test-integrity guard & diff minimality
**What:** Block modifications to test files unless the plan explicitly allows them; Verifier flags any diff touching `test_*` / `*_test` / `tests/`; diff-minimality check rejects formatting churn, debug prints, and unrelated files.
**Why:** "Making tests pass by editing tests" is the classic agent failure mode judges look for. Integrity enforcement is a correctness story in itself.
**How:** Static diff classification before verification; plan-level allowlist; violations feed the recovery ladder as L1 failures.

### 1.4 Isolated adversarial Verifier
**What:** The Verifier sees only the issue, the diff, and test results — never the Implementer's reasoning. Optionally authors 1–2 edge-case tests beyond the reproduction test.
**Why:** Kills confirmation bias; the verifier judges outcomes, not intentions.
**How:** Role-prompt isolation; context builder strips prior agent messages from the Verifier's window.

### 1.5 Environment probe & baseline runnability
**What:** Bootstrap stage detects and runs the target repo's dependency install (`pip install -e .`, `npm ci`, `go mod download`, …) with a timeout, then confirms the test baseline is runnable. If not, the harness degrades to static verification only and says so honestly in `summary.md`.
**Why:** A Verifier that can't run tests is blind; without this the whole pipeline degrades to guessing. Honest degradation beats silent failure.
**How:** Detection table per build system; probe result recorded in the trace and evidence pack.

---

## 2. Efficiency optimizations

### 2.1 Complexity triage / fast path
**What:** The Architect emits a complexity score in its planning call. Below threshold: single-agent direct fix (Locator context → one Implementer pass → Verifier), escalating to the full Manager/overlap-gate machinery only if verification fails.
**Why:** Don't pay hierarchy overhead for a one-line fix. Can halve tokens on easy issues; the escalation itself is a good demo beat.
**How:** Manager interprets the score; fast path shares the same tool runtime and evidence pipeline.

### 2.2 Observation compression (concrete rules)
**What:** Tool outputs are the dominant token sink. Distill test output to failing test names + last ~30 traceback lines; group grep results by file with per-file caps; **collapse older file views** so only the latest read of any file stays in context; truncate harder as the budget governor tightens.
**Why:** Direct hit on the efficiency axis without touching model quality.
**How:** Encoding layer in the tool runtime; compression thresholds tied to budget-governor modes.

### 2.3 Regression test selection
**What:** After each edit, run only tests that import modified modules (selected via the tree-sitter import graph) plus the reproduction test. Full suite runs exactly once at final verification.
**Why:** Saves wall-clock and the tokens spent reading full-suite output on every iteration.
**How:** Import graph already built for the repo-map; selection is a graph reachability query.

### 2.4 Prompt-prefix stability (provider cache friendly)
**What:** Structure every agent prompt as `[system + role + repo-map + fact ledger] → [volatile conversation]` and never reorder the prefix.
**Why:** Major OpenAI-compatible providers cache stable prefixes; zero cost to implement, significant input-cost reduction where caching exists.
**How:** Context builder emits the stable prefix first, byte-identical across calls.

### 2.5 Index cache keyed by commit hash
**What:** Store the tree-sitter/BM25 index under `.harness/index/<repo-sha>/` so repeated runs on the same repo skip re-indexing.
**Why:** Evaluator may run several issues against one repo; index build is pure CPU we don't need to repeat.
**How:** Content-hash key; graceful rebuild on mismatch.

### 2.6 Personalized PageRank on the repo-map
**What:** Rank repo-map symbols by PageRank over the reference graph, with the personalization vector seeded from identifiers extracted from the issue text.
**Why:** Issue-specific repo-map = more relevant context in fewer tokens (aider's approach, sharpened).
**How:** Post-bootstrap computation; seeds refreshed per plan phase.

---

## 3. Robustness against evaluation unknowns

### 3.1 Model-capability probe & dual tool-calling modes
**What:** At startup, probe the prescribed model: native tool-calling support? JSON mode? effective context window? Fall back to a text protocol (structured blocks parsed from the completion) when native tool calls fail.
**Why:** The prescribed model is unknown until evaluation. Teams that hardcode one calling convention break at eval time — this is the single biggest "our harness didn't run" risk.
**How:** Capability table cached per model name; both calling conventions implemented behind one interface.

### 3.2 Loop detector & dead-end ledger
**What:** Detect repetition (same tool call + arguments N times, identical diff produced twice) and treat it as an L1 failure forcing a strategy change. The fact ledger records *dead ends* — hypotheses tried, files ruled out — so re-planning never retreads them.
**Why:** Loops are the main cause of budget exhaustion without progress.
**How:** Hash-based repetition detection in the engine loop; ledger entries injected into re-plan prompts.

### 3.3 Rate limiter in the model client
**What:** Cap concurrent model calls and add 429-aware backoff before the overlap gate fans out parallel specialists.
**Why:** Parallel worktrees mean parallel API calls; without a cap we hit rate limits exactly when parallelism triggers.
**How:** Token-bucket semaphore in the client; config-driven concurrency limit.

---

## 4. Judge-facing differentiators

### 4.1 Trace replay mode & `make report`
**What:** The TUI can replay any `trace.jsonl` with zero API calls; `make report` renders a trace into a single self-contained HTML file.
**Why:** Deterministic, token-free demo path (no live-API nerves on stage), and judges can audit a full run after the fact.
**How:** Replay drives the same TUI views from recorded events; report is a static export.

### 4.2 Localization-recall benchmark in `make test`
**What:** Use public SWE-bench Lite issue text + gold patches to measure whether the Locator's top-k files contain the gold-patch files — no need to run those repos' test suites.
**Why:** "Right files found N% of the time *before any LLM call*" is a metric no other team will show, and it validates the core efficiency claim.
**How:** Offline fixture task; recall@k reported in the test summary.

### 4.3 Best-of-N sampling as gated fallback
**What:** Only when the first candidate fails verification **and** budget remains above 50%: sample two alternative candidates with different localization slices; keep the one passing the most tests.
**Why:** Improves correctness without paying N-times cost on every task — the gate keeps it compatible with the efficiency axis.
**How:** Manager-gated branch in the execution pipeline; all candidates logged to the trace.

---

## 5. Priority matrix

| Priority | Items | Rationale |
|---|---|---|
| **Must-have** | 1.1, 1.2, 1.5, 3.1 | The difference between "runs and produces verified patches" and "fails at eval time" |
| **High value** | 1.3, 2.1, 2.2, 2.3, 3.2 | Direct hits on scored axes; each ≤ 1 day of work |
| **Differentiators** | 4.1, 4.2, 1.4 | Presentation and evidence; low effort, high judge impact |
| **Stretch** | 2.4, 2.5, 2.6, 3.3, 4.3 | Real but marginal; take if the timeline holds |

**Trade-off note:** items 1.1, 1.4, and 4.3 add model calls. They must live under the budget governor: the reproduction test is worth its cost every time, the adversarial Verifier most of the time, best-of-N only when there is slack.
