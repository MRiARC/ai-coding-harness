# DevOps Specialist Playbook

## CORE PRINCIPLES
- Pipelines are code: versioned, reviewed, tested like application code. A pipeline you can't re-run from a clean checkout isn't a pipeline.
- Hermetic builds: deterministic inputs → reproducible outputs; lockfiles pinned; no network surprises mid-build.
- 12-Factor deployment: config in env, stateless processes, disposable containers, build/release/run separated.
- DORA metrics are the scoreboard: deployment frequency, lead time, change-failure rate, MTTR — improve one at a time.
- Secrets live in a vault or secret manager, injected at runtime — never in images, repos, logs, or CI variables that echo.
- Progressive delivery: canary/blue-green with automated rollback on SLO breach. Deployment ≠ release.

## CHECKLIST
- [ ] CI runs lint + typecheck + tests on every PR; main is always deployable
- [ ] Build artifacts immutable and versioned (digest, not :latest)
- [ ] Health checks (liveness + readiness) defined and actually probed
- [ ] Rollback tested: previous artifact redeploys green in one command
- [ ] Logs structured, leveled, and correlated by request ID
- [ ] Resource limits + graceful shutdown configured

## PATTERNS
- Trunk-based development with short-lived branches; feature flags for incomplete work
- Blue-green for instant rollback; canary for blast-radius measurement
- Infrastructure as code with plan-review-apply; drift detection in CI
- Cache dependencies by lockfile hash; make the cache key part of the contract

## ANTI-PATTERNS
- Snowflake servers configured by hand
- `docker run` with :latest in production manifests
- Manual steps between green CI and production
- Alerts without runbooks; dashboards nobody opens
- Copy-pasted YAML across services with no shared module

## DECISION HEURISTICS
- Flaky CI step? Quarantine visibly and fix within a day — a red main is an outage
- Deploy failed? Roll back first, debug second
- New dependency in the image? Pin, scan (CVEs), and record why it exists
- Infra change? Plan output reviewed by a second pair of eyes, applied off-peak

## REFERENCES
- 12-Factor App — 12factor.net
- DORA — dora.dev
- Google SRE workbook — sre.google/workbook
- OpenSSF scorecard — github.com/ossf/scorecard
