# Backend API Specialist Playbook

## CORE PRINCIPLES
- Model resources, not endpoints: nouns with stable identities, verbs via HTTP methods. Consistency across the API beats local cleverness.
- Idempotency where money/state is involved: POST with idempotency keys, PUT semantics truly idempotent, retries safe by design.
- Validate at the edge, trust internally: one strict validation layer (types, lengths, enums, cross-field), typed models inside.
- Errors are part of the contract: stable error codes/envelopes, actionable messages, correct status codes (400 vs 422 vs 409 vs 404).
- Authz on every entry point: authentication ≠ authorization. Deny by default; check object-level ownership, not just role existence.
- Latency budget per endpoint: know your p95, kill N+1 queries, paginate every collection, cache the cacheable with explicit invalidation.

## CHECKLIST
- [ ] Request/response schemas typed and validated (Pydantic/zod/etc.)
- [ ] Pagination, filtering, sorting on every collection
- [ ] Versioning strategy stated (URL/header) and breaking changes gated
- [ ] Rate limiting + request size caps
- [ ] Structured logs with request IDs; no PII/secrets in logs
- [ ] Contract tests pin the public surface

## PATTERNS
- Expand-contract for API changes; deprecate before remove
- Cursor pagination for large/high-churn collections; offset only for small sets
- Optimistic concurrency (ETag/If-Match) for collaborative updates
- Webhook + retry-with-backoff for async integrations; sign your payloads

## ANTI-PATTERNS
- Chatty APIs (one HTTP call per UI widget)
- Business logic in controllers (thin controllers, fat services/domain)
- Booleans in URLs (`?delete=true`) instead of explicit endpoints
- Leaking internal IDs/stack traces to clients
- Long-lived tokens with no revocation path

## DECISION HEURISTICS
- Two services need the same data synchronously? Extract a shared module or accept the coupling explicitly — never duplicate silently
- Latency dominated by DB? Fix the query before adding cache layers
- New endpoint resembling an existing one 80%? Generalize carefully or accept duplication for decoupling

## REFERENCES
- OWASP API Security Top 10 — owasp.org/API-Security
- RESTful API design notes — github.com/WhiteHouse/api-standards
- Microsoft REST API Guidelines — github.com/microsoft/api-guidelines
