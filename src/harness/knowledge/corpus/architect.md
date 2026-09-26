# Architect Playbook

## CORE PRINCIPLES
- Start monolith-first: a well-modularized monolith beats premature microservices; split along DDD bounded contexts only when scale or team topology forces it.
- Every architecture decision gets an ADR (Architecture Decision Record): context, options, decision, consequences. Decisions are reversible until proven otherwise — prefer reversible choices.
- Design with the C4 model: Context → Containers → Components → Code. Communicate at the level your audience needs.
- Coupling down, cohesion up: modules that change together live together; modules that don't, don't share a package.
- 12-Factor for anything deployed: config in env, stateless processes, disposability, dev/prod parity.
- Failure is a feature of distributed systems: design blast-radius isolation (bulkheads, timeouts, retries with backoff, circuit breakers) before adding features.
- Observability is architecture: RED (rate/errors/duration) for services, USE (utilization/saturation/errors) for resources, structured logs from day one.
- Security by design: trust boundaries drawn explicitly (STRIDE), least privilege per component, secrets never in code or images.

## CHECKLIST
- [ ] Interfaces defined before implementations (contracts, not concretions)
- [ ] Data flow diagrammed: where does state live, who owns it, how does it move
- [ ] Failure modes enumerated per boundary (timeout, partial failure, retry storm)
- [ ] Scaling story per component (what doubles first: traffic, data, team)
- [ ] Migration path from the current state (strangler fig, expand-contract)
- [ ] Production-readiness: health checks, graceful shutdown, config validation, runbooks
- [ ] No single point of undeployability: can you ship one module without the world

## PATTERNS
- Strangler fig for incremental rewrites; expand-contract for schema/API changes
- Cache-aside with explicit invalidation; queues to decouple bursty work
- Ports & adapters (hexagonal): domain logic depends on interfaces, not frameworks
- Saga (orchestrated or choreographed) for cross-service transactions; avoid distributed 2PC

## ANTI-PATTERNS
- Distributed monolith: microservices that must deploy together
- Golden hammer: one storage/queue tech for every shape of problem
- Resume-driven architecture: Kafka+K8s+mesh for a CRUD app with 3 users
- Big design up-front: 60-page specs before a line of code
- Ignoring data: schema and access patterns drive more than service diagrams

## DECISION HEURISTICS
- Complexity score 1-4: keep it boring; 5-7: document decisions, test seams; 8-10: spike first, decide with evidence
- If a boundary is unclear after two attempts, draw the data model first
- Estimate blast radius before velocity: "what breaks if this fails" beats "how fast can this go"
- Prefer boring technology for the core; innovate on the edge only

## REFERENCES
- C4 model — c4model.com
- ADRs — adr.github.io
- 12-Factor App — 12factor.net
- Strangler fig application — martinfowler.com/bliki/StranglerFigApplication.html
- Production-readiness checklists — agamitechnologies.com (2026 guide); google.com/sre/checklists
