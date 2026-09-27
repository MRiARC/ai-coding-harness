# Evaluation Runbook

Everything an evaluator (or teammate) needs to take the harness from a fresh
clone to a verified evidence pack. Mirrors the official procedure and was
rehearsed in a clean-room clone (see §7).

## 1. The graded interface

```bash
git clone <TEAM_REPOSITORY> && cd <repo>
export AI_API_KEY="<PROVIDED_API_KEY>"
make setup     # venv + pinned deps + doctor (warn-only about everything optional)
make run       # THE entry point - see §2 for what it does with the issue
make test      # offline suite: 329 tests, 100% coverage enforced, no key needed
make clean     # artifacts only (keeps .venv)
```

## 2. Supplying the issue (all protocols supported)

`make run` picks the issue up from, in priority order:

1. `--issue "text"` / `--issue-file path` (`harness solve …` directly)
2. `HARNESS_ISSUE` / `HARNESS_ISSUE_FILE` environment variables
3. **piped stdin**: `echo "issue text" | make run`
4. nothing supplied → health summary + latest-evidence pointer (headless)

Target repository: the one the issue refers to. Default is the harness's own
cwd; point elsewhere with `HARNESS_TARGET_REPO=/path/to/target` or `--repo`.

```bash
# the evaluation shape, end to end:
echo "app.greet() should return 'hello' when called" | make run
# -> outcome: VERIFIED: all tasks completed and gates passed
# -> run: <run-id>  evidence: results/<run-id>
```

Exit codes: `0` verified · `1` gates failed (see test-report.md) ·
`2` bad invocation · `3` credentials missing.

## 3. What comes out (evidence pack)

`results/<run-id>/`:

| File | Contents |
|---|---|
| `patch.diff` | the working-tree change the specialists produced |
| `trace.jsonl` | every decision: assignment, model calls (hashed), tool calls, results |
| `test-report.md` | the five verification gates with per-stage durations |
| `token-report.json` | tokens per agent, efficiency per 1k tokens, phase timings |
| `summary.md` | human narrative: issue → plan → verification → flags |

Inspect without rerunning: `harness replay [RUN_ID]` (offline).

## 4. Model configuration

`harness.yaml` (copy `config.example.yaml`) pins the prescribed model:

```yaml
models:
  default:
    provider: openai-compatible   # or openai | anthropic | google
    name: <prescribed-model>      # slot the organizers' model here
    api_key_env: AI_API_KEY       # the key itself is NEVER in config
    base_url: https://<endpoint>  # if the prescribed endpoint differs
```

Changing models is a config edit only. Verify the endpoint without spending
a full run: `harness doctor --probe-model` (one tiny call, warn-only).

## 5. Offline / demo mode

`HARNESS_DEMO=1 make run < issue` runs the whole pipeline on a scripted
model with zero credentials. Evidence is labeled `DEMO MODE` in flags and
summary - for demos only, never for graded evaluation.

## 6. Troubleshooting

| Symptom | Meaning |
|---|---|
| exit 3, "AI_API_KEY is not set" | the configured (non-fake) model has no credential - export it |
| exit 1, "NOT VERIFIED" | a verification gate failed - `test-report.md` says which |
| "no evidence pack found" | `harness replay` ran before any solve - run the pipeline first |
| health summary instead of solving | no issue was supplied; pipe it or set `HARNESS_ISSUE` |

## 7. Rehearsal (this runbook, verified)

Executed 2026-09-26 in a fresh clone on a clean branch:

```
make setup           ✅ venv from scratch, doctor green
export AI_API_KEY=…  ✅ doctor confirms
echo "<issue>" | make run   ✅ VERIFIED + evidence pack
harness replay       ✅ full decision trace rendered
make test            ✅ 329 passed, 100.00% coverage enforced
```

The rehearsal caught and fixed three real defects (doctor's unconditional
key warning, a test patching the wrong namespace, stdin fakes missing
`read()` under piped-stdin inheritance) - which is exactly why it exists.

## Token benchmark (M5, issue #64)

`make bench-tokens` (or `harness bench`) runs the offline fixture end-to-end
through the real pipeline — FakeProvider, no credentials — and prints the
per-agent token spend. It is the measuring stick for every context-management
change (issues #60–#63):

```bash
harness bench --save-baseline          # record current spend (docs/evidence/bench-baseline.json)
# ... make your optimization ...
harness bench                          # compare against the saved baseline
harness bench --ref feat/milestone-4   # or A/B directly against any git ref
harness bench --json-out delta.json    # machine-readable per-agent delta
```

Baseline `--ref` uses a detached temporary git worktree and cleans it up.
Token counts come from the deterministic estimator over byte-identical
prompts, so identical code produces identical numbers on the same machine.
