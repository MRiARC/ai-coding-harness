# Database Specialist Playbook

## CORE PRINCIPLES
- Schema is a public API: columns and constraints outlive the code that uses them. Name for the domain, constrain in the DB (NOT NULL, UNIQUE, FK) — the database is the last line of defense.
- Every destructive operation is reversible until proven impossible: expand-contract migrations, shadow tables, backups verified before DROP/TRUNCATE.
- Measure before optimizing: EXPLAIN the plan; an index without a query is a write-tax.
- Transactions at the boundary: multi-statement consistency inside one transaction; know your isolation level and its anomalies.
- Migrations are code: versioned, reviewed, tested up AND down, runnable online on a live table (no long locks).

## CHECKLIST
- [ ] Indexes match actual query predicates (columns, order, selectivity)
- [ ] No N+1: check the query pattern that loops
- [ ] Foreign keys with intentional ON DELETE behavior
- [ ] Timestamps created_at/updated_at on every operational table
- [ ] Migration tested on a copy of production-scale data (or representative volume)
- [ ] Down-migration written and rehearsed

## PATTERNS
- Expand-contract: add new column → dual-write/backfill → switch reads → drop old
- Online migrations: batched backfills, lock_timeout + retries, CREATE INDEX CONCURRENTLY
- Soft deletes only with explicit product need (and uniqueness handling)
- Read replicas for read-heavy paths — after fixing the queries

## ANTI-PATTERNS
- EAV (entity-attribute-value) unless the schema is genuinely dynamic
- Storing JSON blobs you then query with fixed keys (use columns)
- ORM lazy-loading inside loops (N+1)
- One migration doing schema + backfill + switch in a single lock window
- TRUNCATE/DROP without a rehearsed restore

## DECISION HEURISTICS
- Slow query? EXPLAIN first; index second; denormalize third; cache last
- New relation? Ask: is this aggregation mutable (table) or derived (view/materialized view)
- Data loss risk in any step? Stop and write the restore procedure first
- Count vs wall-clock: a 50ms indexed query beats a 5ms cached one you can't invalidate

## REFERENCES
- Use-the-index-luke — use-the-index-luke.com
- Postgres docs: concurrency control, indexes — postgresql.org/docs
- Expand-contract — martinfowler.com/articles/evolvable-databases.html
