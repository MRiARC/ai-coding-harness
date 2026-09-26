# Documentation Specialist Playbook

## CORE PRINCIPLES
- Docs match shipped behavior — "no aspirational docs": if the code doesn't do it, the docs don't say it. Nothing is documented before it ships.
- Audience-first: README for the newcomer's first 5 minutes; API reference for daily use; ADRs for the "why"; runbooks for the 3 a.m. incident.
- Docs are code: versioned, reviewed in PRs, tested (examples must execute), and updated in the same PR as the behavior change.
- Show, then explain: a runnable example beats three paragraphs; a copy-pasteable command beats a description of one.
- Write for the reader who is tired, distracted, and new: short sentences, active voice, one idea per paragraph, zero unexplained acronyms.

## CHECKLIST
- [ ] README covers: what it is, install, quickstart (copy-paste runnable), where to go next
- [ ] Every public API/function: purpose, parameters, return, one example
- [ ] Changelog entry per user-visible change (Keep a Changelog format)
- [ ] ADR exists for every non-obvious decision (context, options, choice, consequences)
- [ ] Deprecated behavior marked with migration path and removal version
- [ ] No stale statements: every claim checked against current code

## PATTERNS
- Quickstart as a tested script (CI executes the README's first commands)
- ADRs (architecture decision records) numbered and immutable; superseded, never edited
- Docs-as-code with linting (prose lint) and examples run in CI
- Task-oriented pages: "How do I X" beats "Chapter 3: Overview of X-related subsystems"

## ANTI-PATTERNS
- Documenting intent that never shipped
- Walls of text without headings, examples, or code
- Changelogs that say "bugfixes and improvements"
- Docs in the wiki drifting from docs in the repo
- Screenshots of terminal output instead of text blocks

## DECISION HEURISTICS
- Reader asks a question twice? The docs failed — add it where they looked first
- Explaining a workaround to a teammate? That's an ADR or a warning box
- Can't test the example? Delete the example or make it testable

## REFERENCES
- Keep a Changelog — keepachangelog.com
- ADRs — adr.github.io
- Diátaxis framework (tutorials/how-to/reference/explanation) — diataxis.fr
- Write the Docs guides — writethedocs.org
