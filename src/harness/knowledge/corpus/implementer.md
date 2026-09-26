# Implementer Playbook

## CORE PRINCIPLES
- Minimal diff discipline: change only what the subtask requires. Every extra line is review surface, regression risk, and merge-conflict fuel.
- Kent Beck's rule: "make the change easy (refactor), then make the easy change" — but only when the refactor is small and local.
- Conform to the file you're editing: its naming, error-handling style, import order, and formatting win over your personal taste.
- Error handling at boundaries: validate inputs where they enter (HTTP, CLI, queue), fail with actionable messages, never swallow exceptions silently.
- YAGNI: no speculative generality, no config flags for one caller, no abstractions with a single implementation.
- The diff tells the story: if a reviewer can't reconstruct the WHY from the diff + commit message, the change is incomplete.

## CHECKLIST
- [ ] Edit applied from the localization artifact (not a guess)
- [ ] Syntax gate passed (parse/compile) before any test run
- [ ] Only subtask-scoped files touched — never tests unless explicitly told
- [ ] No debug prints, commented-out code, or formatting churn
- [ ] Error paths handled, not just the happy path
- [ ] Existing tests for the touched code still pass

## PATTERNS
- Search/replace edits over line-number patches (drift-proof)
- Whole-file rewrite only for files < 50 lines
- Guard clauses early to flatten nesting
- Extract-function when a fix needs three nested conditions in one method

## ANTI-PATTERNS
- Drive-by refactors riding on a bug fix
- Defensive re-implementations of standard-library functions
- Silent catch blocks (`except: pass`) — they turn bugs into ghosts
- Changing public API signatures without checking callers
- Magic numbers where the surrounding code uses named constants

## DECISION HEURISTICS
- Uncertain between two designs? Pick the one with fewer new concepts.
- Fix touching > 3 files for complexity < 5: the localization is wrong — stop and re-scope.
- If the edit needs a comment to explain WHAT it does, rewrite the code; comments explain WHY only.

## REFERENCES
- Kent Beck — "Make the change easy, then make the easy change"
- OWASP secure coding quick reference (input validation, output encoding)
