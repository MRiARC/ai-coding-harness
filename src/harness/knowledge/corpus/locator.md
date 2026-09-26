# Locator Playbook

## CORE PRINCIPLES
- Never guess: every claim ("this is where the bug is") cites a file:line and the evidence that put you there (search hit, import chain, stack trace frame).
- Work the funnel: repo map → file shortlist → symbol search → line range. Cheapest query that shrinks the space wins.
- Follow the data: the buggy value enters somewhere, transforms, and surfaces. Trace the data path, not the call stack alone.
- Blast radius = imports: a function imported by 40 modules behaves differently under change than a private helper.
- Read the tests: tests encode intended behavior and often pinpoint the exact function the issue touches.
- Entry points first: routes/CLI handlers/event consumers for behavior bugs; schema/serializers for data bugs; stack-trace frames for crashes.

## CHECKLIST
- [ ] Exact file(s) + line ranges identified (not just files)
- [ ] For each hit: WHY it is relevant to this issue in one line
- [ ] Symbols named precisely (class.method, function) — the implementer shouldn't re-search
- [ ] Related code checked for the same pattern (the bug rarely lives alone)
- [ ] Search evidence preserved: queries tried, hits found, dead ends noted

## PATTERNS
- Grep for the error string first; identifiers second; concepts last
- Symbol search (class/method definitions) beats text search once you know the vocabulary
- git log/blame on suspicious files reveals hot paths and recent regressions
- Layer bisection: half the stack (route → service → storage), decide, repeat

## ANTI-PATTERNS
- Reading entire large files when a ranged read answers the question
- Reporting a file with no line evidence ("it's probably in utils.py")
- Stopping at the first hit when the same symbol appears in five modules
- Searching for the fix instead of the fault

## DECISION HEURISTICS
- Stack trace present → start at the deepest project frame, then walk up
- Issue mentions a UI symptom → start at the route/component that renders it
- Issue mentions wrong data → start at the schema/model and follow writes
- Two candidate files → read both fully; half-context is worse than none

## REFERENCES
- SWE-bench localization literature (Agentless, moatless-tools)
- Code navigation heuristics — your editor's "find references" is the model
