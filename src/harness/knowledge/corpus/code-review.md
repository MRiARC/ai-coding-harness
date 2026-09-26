# Code Review Specialist Playbook

## CORE PRINCIPLES
- Reviews grade the change, not the author: ask questions, propose alternatives, classify every finding (block / should-fix / nit) so the author can triage.
- Correctness before style: boundary conditions, error paths, concurrency, authz, data loss — in that order. Formatting is a tool's job.
- Evidence per finding: point to the line, describe the failure scenario ("if `ids` is empty, this raises"), and offer the fix shape.
- Small diffs get deep reviews: a 100-line diff gets line-by-line; a 2,000-line diff gets a design discussion first.
- The test review IS the review: what would these tests catch, what would they miss, and do the assertions actually assert?
- Non-blocking findings never block: advisory issues with evidence, filed so they're trackable.

## CHECKLIST
- [ ] Does the diff do what it claims (read the issue/description first)?
- [ ] Boundaries: empty/None/negative/huge inputs handled
- [ ] Error paths: exceptions raised, caught, surfaced — no silent swallows
- [ ] Concurrency: shared state, locks, ordering assumptions
- [ ] Security: injection, authz, secrets in diffs, unsafe deserialization
- [ ] Tests: would fail without the change? Miss a branch?
- [ ] Dead code, debug prints, TODO density, leftover experiments
- [ ] Performance: N+1, unbounded loops/collections, hot-path allocations

## PATTERNS
- Layered pass: skim for shape → line-by-line for logic → tests → naming/docs
- Ask "what test would fail if this line were deleted?" per non-trivial line
- Record findings as structured advisories (file:line, severity, evidence, suggested fix)

## ANTI-PATTERNS
- Style opinions without a lint rule backing them
- "Looks good" on a 900-line diff
- Rewriting the author's design in comments instead of discussing trade-offs
- Blocking on nits while missing a data-loss bug

## DECISION HEURISTICS
- One data-loss/authz/injection finding → BLOCK regardless of size
- Third nit in one function → suggest a follow-up refactor issue instead of piling on
- Can't understand the diff in 10 minutes? That's the first finding: split the PR
- Test file changed? Review the assertions line-by-line — this is where integrity dies

## REFERENCES
- Google Engineering Practices (code review) — google.github.io/eng-practices/review
- Conventional Comments — conventionalcomments.org
