# Milestone 3 (Tools, Verification, Security, Monitoring, TUI) — Review Report

**PR reviewed:** #45 "Milestone 3: Tools, Verification Pipeline, Security, Monitoring & TUI (issues 3.1–3.16)" (`feat/milestone-3`, commits `bd1bec0`…`61716c6`)
**Reviewed / merged:** 2026-09-26 by automated review (ZCode) on behalf of the repo owner
**Verdict:** ✅ **Approved and merged into `main`** (merge commit `17162a9`)

> Base-branch note: like #44, this PR was opened against a feature branch
> (`feat/agents`). Base corrected to `main` before merge so CI validated the
> real target and the merge landed directly.

---

## 1. Verification

| Check | Result |
|---|---|
| Offline suite | ✅ **329 passed**, 100% coverage enforced on 2,735 statements (up from 199/1,513) |
| Lint + strict mypy | ✅ clean (82 files) |
| CI (Python 3.11 + 3.12) | ✅ success on final head `61716c6` |
| Manual code review | ✅ all new modules read (tools ×5, engine ×2, security ×3, monitoring ×2, verification ×2, CLI, TUI) |

**Review fixes applied during the cycle** (the teammate landed equivalent fixes in `61716c6` while review fixes were in flight): a `ruff format` nit in `cli.py` and stale `FakeStdin` test doubles that lacked `read()` once the new stdin issue-intake landed. Caught locally on Python 3.14 before CI completed.

## 2. What landed (~4,100 lines, 35 files)

| Area | Contents |
|---|---|
| **Tool runtime** (`tools/`) | 12-tool registry (5 Tier-1 / 5 Tier-2 / 2 Tier-3): `read_file`, `list_dir`, `search_text` (60-match/200KB caps), `git_status/log/branch/diff`, `apply_edit`, `syntax_check`, `run_tests` (pytest/npm/make auto-detect), `code_execution`, `security_scan` |
| **Edit format** | `apply_edit` = **search/replace** (improvements §1.2 must-have) with whitespace-tolerant fallback, CRLF preservation, backups to `.harness/backups/`, and unified-diff output for the trace |
| **Sandbox** | No shell interpolation, hard timeouts, 20KB output cap, `RLIMIT_CPU` 30s + `RLIMIT_AS` 512MB via preexec — the eval-mode stand-in for the spec's Docker sandbox |
| **Security** (`security/`) | `input_guard` (8 injection patterns, path confinement incl. symlink escapes, command allowlist + metacharacter rejection), `secret_scanner` (diff scan + path policy, blocking gate), `audit.py` (**SHA-256 hash-chained append-only JSONL** — tamper-evident with zero infra) |
| **Verification** (`verification/`) | 5 stages adapted to eval mode: syntax self-check → local full suite → AST smell pass (non-blocking) → secret scan (blocking) → Architect LLM final verdict; stops at first blocking failure |
| **Pipeline** (`engine/pipeline.py`) | End-to-end orchestration: injection scan → Architect (analyze + decompose) → Manager batches (**disjoint file-sets run concurrently** via `asyncio.gather`) → recovery ladder per subtask → verification → evidence pack |
| **Evidence** (`engine/evidence.py`) | `results/<run-id>/`: `patch.diff`, `trace.jsonl` (audit spine), `test-report.md`, `token-report.md`, `summary.md` — the "evidence over claims" deliverable |
| **Monitoring** (`monitoring/`) | `metrics.py` (per-stage/per-agent), `health.py` (health checks + opt-in `--probe-model` capability probe) |
| **Eval-day hardening** | `harness solve` with **all four Foreman §7 intake paths** (`--issue`, `--issue-file`, `HARNESS_ISSUE(_FILE)`, piped stdin); `HARNESS_DEMO=1` scripted-provider demo mode (token-free); `harness replay` for offline trace replay; Textual TUI cockpit over the live evidence with headless fallback |

## 3. Notes (non-blocking)

1. **Reproduction-first baseline not yet in** (improvements §1.1): Stage 2 runs the target repo's suite but doesn't record pre-existing failures to exempt them. The single most valuable milestone-4 item.
2. **Autoscaling not wired** (as agreed, deferred): `assign_specialists` ranks a static config-built pool; saturation → "add collaborators" is still only a status string.
3. `pipeline._run_batch` fallback `next(iter(self._agents))` could pick the architect if no specialists are configured — edge case worth tightening.
4. Local dev ran on Python 3.14; CI matrix (3.11/3.12) is the compatibility authority.

## 4. Related

- [Milestone 1 review](2026-09-26-milestone1-foundation-review.md) · [Milestone 2 review](2026-09-26-milestone2-agents-review.md) · [Live agent verification](2026-09-26-live-agent-verification.md)
- Issues #25–#41 (Milestone-3 scope) close via this PR's body.
