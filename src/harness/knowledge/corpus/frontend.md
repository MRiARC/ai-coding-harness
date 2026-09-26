# Frontend Specialist Playbook

## CORE PRINCIPLES
- Component boundaries follow data + behavior, not layout accidents: one reason to change per component.
- State colocation: state lives as close to its consumers as possible; lift only when siblings genuinely share.
- Accessibility is functional correctness: semantic HTML first, keyboard paths, labels, focus management, WCAG AA contrast.
- Every async surface has four states: loading, empty, error, success. Shipping three of four is shipping a bug.
- Design tokens over hardcoded values: spacing, color, typography from the design system; the pattern file you're editing is the source of truth.
- Bundle discipline: code-split routes, lazy-load heavy widgets, measure before optimizing.

## CHECKLIST
- [ ] Loading, empty, error, success states all implemented
- [ ] Keyboard navigation + visible focus for interactive elements
- [ ] Forms: labels, validation messages, disabled-while-pending
- [ ] No layout shift from async content (skeletons/dimensions)
- [ ] Component matches existing patterns (composition, prop naming, file layout)
- [ ] Tests: behavior via user-visible interactions, not implementation details

## PATTERNS
- Controlled inputs for validation-heavy forms; uncontrolled for simple ones
- Derived state computed, not duplicated; single source of truth per datum
- Optimistic updates with rollback on failure — only with idempotent APIs
- Portal for overlays; focus trap in modals; aria-live for async announcements

## ANTI-PATTERNS
- Prop drilling 4+ levels where context/store is warranted
- Effects syncing state that could be derived during render
- Giant "screen" components with local business logic
- Pixel-value hardcoding where tokens exist
- Deleting ARIA attributes because "tests get noisy"

## DECISION HEURISTICS
- Two components share markup but diverge in behavior? Compose, don't parameterize
- Re-render storm? Memoize the expensive subtree, then fix the state shape
- Third-party widget? Wrap it behind your own component boundary day one

## REFERENCES
- WCAG 2.2 quick reference — w3.org/WAI/WCAG22/quickref
- React docs: you-might-not-need-an-effect — react.dev/learn/you-might-not-need-an-effect
- web.dev Core Web Vitals — web.dev/vitals
