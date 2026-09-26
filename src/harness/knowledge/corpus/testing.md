# Testing Specialist Playbook

## CORE PRINCIPLES
- Reproduce first, fix second: turn every reported bug into a failing test before touching production code. The test is the spec.
- BDD for behavior: given/when/three-then scenarios for anything a stakeholder would describe.
- Test data builders over fixtures-from-hell: deterministic factories, explicit seeds, no shared mutable state between tests.
- Mock/stub only at boundaries you own (network, clock, filesystem, random) — never mock the unit under test.
- Test code is production code: named well, refactored, DRY-ish but readable top-to-bottom.
- Assertion density: every test earns its existence by failing for exactly one reason.

## CHECKLIST
- [ ] New test fails for the stated reason (verify by reverting the fix mentally or literally)
- [ ] Runs in isolation AND in the full suite (no ordering coupling)
- [ ] Deterministic: no time.Now(), no network, no random without a seed
- [ ] Error paths covered, not just the golden path
- [ ] Edge inputs: empty collections, None/nil, boundary integers, unicode

## PATTERNS
- Arrange-Act-Assert; Given-When-Then for stakeholder-visible behavior
- Property-based testing: Hypothesis (Python), fast-check (JS), QuickCheck lineage
- Parameterized tables for input/output matrices
- Approval/golden files for serializers and renderers — with a documented diff-review flow

## ANTI-PATTERNS
- Assertion-free smoke tests claiming coverage
- Copy-pasting a test 5 times with one literal changed (parameterize instead)
- Testing mocks instead of behavior
- "Known flaky" tags as a lifestyle

## DECISION HEURISTICS
- Bug report vague? Write the test that WOULD have caught it; that test is the acceptance criterion
- Test needs a sleep? Find the event/poll/timeout mechanism instead
- Coverage gap on a critical path? Add the test before the feature ships

## REFERENCES
- Test pyramid — martinfowler.com/bliki/TestPyramid.html
- Hypothesis — hypothesis.works
- TDD-Bench Verified (arXiv 2024)
- xUnit Test Patterns (Meszaros) — test doubles and fixtures taxonomy
