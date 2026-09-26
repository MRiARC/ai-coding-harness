# Live-model verification — claude-sonnet-4.5

Recorded evidence packs from real `harness solve` runs against a live
OpenAI-compatible endpoint (model: `claude-sonnet-4.5`, temperature 0).
No credentials are stored here — the key lives in the `AI_API_KEY`
environment variable only, by design.

## `260eea0d3990/` — the Milestone-4 verification run

Target: a fresh repository with a genuine bug (`add()` computed `a - b`;
`test_add` failing) and a passing `test_greet`.

- **Outcome:** `VERIFIED: all tasks completed and gates passed`
- **Patch:** one line — `return a - b` → `return a + b`
- **Target tests:** 2/2 green after the patch
- **Gates:** 5/5 PASS (self-check, local tests, code review advisories,
  secret scan, Architect final review with written rationale)
- **Tokens:** ~112k total (architect 33k / locator 14k / verifier 64k)
- **Phases:** architect 10.8s · specialists 31.8s · verification 5.1s

Reproduce: `harness solve --issue "..." --repo <target>` with
`harness.yaml` pointed at any OpenAI-compatible endpoint.

## `b7fa5d658d71/` — the first VERIFIED run (feat/milestone-3)

Same target and issue; the run that proved the structured tool-call
conversation fix end to end. Kept for comparison of the journey.

## What these packs demonstrate

1. The evaluator's contract works against a **live, tool-capable model**
   through an OpenAI-compatible proxy — not just the offline FakeProvider.
2. Every claim in `summary.md` is backed by the auditable
   `trace.jsonl` (assignments, model calls, tool calls, gate results).
3. `test-report.md` gates are mechanical: the local test suite of the
   TARGET repository is the ground truth, not the model's claim.
