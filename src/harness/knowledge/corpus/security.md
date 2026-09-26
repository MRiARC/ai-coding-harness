# Security Specialist Playbook

## CORE PRINCIPLES
- Fail secure: on error, deny. Default-deny authorization, allowlist input validation (never blocklist), explicit trust boundaries.
- Defense in depth: one control per layer — validate at the edge, re-check at the service, constrain in the database.
- Least privilege everywhere: service accounts scoped to one task, DB users per service with minimal grants, short-lived credentials.
- Secrets are env/vault-only: never in code, config files, logs, images, or error messages. Key rotation rehearsed, not theoretical.
- Don't roll your own crypto: standard libraries, vetted parameters, and never home-grown schemes for auth, hashing, or tokens.
- Threat-model the change: STRIDE the new surface — what can be spoofed, tampered, repudiated, disclosed, denied, elevated?

## CHECKLIST (OWASP Top 10 lens)
- [ ] A01 Broken access control: object-level authz on every fetch/mutation
- [ ] A02 Cryptographic failures: TLS everywhere, strong hashing (argon2/bcrypt), no sensitive data in URLs
- [ ] A03 Injection: parameterized queries, no string-built commands, output encoded
- [ ] A04 Insecure design: misuse cases considered, rate limits on sensitive flows
- [ ] A05 Misconfiguration: debug off, default creds removed, headers (CSP, HSTS) set
- [ ] A06 Vulnerable components: dependency scan clean or triaged
- [ ] A07 Auth failures: lockout, session expiry, secure cookie flags
- [ ] A08 Integrity: signed payloads, CI artifacts verified
- [ ] A09 Logging: auth events logged, no secrets in logs
- [ ] A10 SSRF: outbound URLs validated against allowlists

## PATTERNS
- Parameterized queries / ORMs as the only SQL path
- Centralized authz middleware + explicit object-ownership checks
- Secret scanning in CI (pre-commit + push barriers)
- Signed webhooks, short-lived JWTs with rotation, CSP without unsafe-inline

## ANTI-PATTERNS
- Security review as a final-phase gate instead of a per-change reflex
- Home-rolled rate limiting on in-memory state in a multi-replica deployment
- "Internal only" as an access-control strategy
- Error messages that double as oracle (stack traces to clients)
- Trusting client-side validation as a security control

## DECISION HEURISTICS
- New input path? Assume hostile until validated and encoded at output
- New privileged operation? Ask who can call it, from where, and what it audits
- Secret spotted in a diff? Block immediately, rotate the value — removal is not revocation
- Can't name the threat model for a feature? That IS the finding

## REFERENCES
- OWASP Top 10 — owasp.org/Top10
- OWASP ASVS — owasp.org/www-project-application-security-verification-standard
- STRIDE — learn.microsoft.com/azure/security/develop/threat-modeling-tool-threats
- OWASP Cheat Sheet Series — cheatsheetseries.owasp.org
