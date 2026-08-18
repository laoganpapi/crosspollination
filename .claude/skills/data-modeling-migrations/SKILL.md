---
name: data-modeling-migrations
description: Relational schema design and migration discipline (Postgres) — constraints, key choice, timestamps, zero-downtime changes. Load when designing tables, writing migrations, choosing primary keys, or changing schema on a live system. Not for query optimization or analytics modeling.
---

# Data modeling and migrations

## Constraints as the last line of defense

The app will have bugs; the schema must not.

- Every column `NOT NULL` unless there's a documented reason. Nullable-by-default is the most common modeling defect.
- Every relationship a real `FOREIGN KEY` with an explicit `ON DELETE` (`RESTRICT` default; `CASCADE` only for true child rows). Index every FK column — Postgres does not do it automatically.
- `UNIQUE` on every natural invariant (one membership per user per group). Enforced in the database — two concurrent requests race past any app-level check.
- `CHECK` for domain rules: `amount >= 0`, `extension_count <= max`, `expires_at > created_at`.
- Enums: `text` + CHECK constraint by default — native Postgres enums resist value removal. A lookup table only when values carry data or users edit them.

## Keys and timestamps

- Primary keys: `bigint GENERATED ALWAYS AS IDENTITY` or UUIDv7 (time-ordered, avoids UUIDv4's index-fragmentation cost). One scheme for the whole schema.
- Never UUIDv4 as a clustered key; never bigints in public URLs (enumeration) — expose UUIDv7 or a slug. Note UUIDv7 leaks creation time; fine almost always.
- `timestamptz` always, never `timestamp`. UTC stored, converted at the edge. `created_at`/`updated_at` on every table, maintained by one mechanism (trigger or ORM), not both.
- Money: `numeric` or integer minor units. Never float.

## Soft delete

- Only where undo or audit genuinely requires it. Costs: every query needs the `deleted_at IS NULL` filter (one miss is a data leak), unique constraints become partial indexes, FKs still reference "deleted" rows.
- Default instead: hard delete plus an audit/history table. Never soft-delete schema-wide "just in case".

## Migration discipline

- Every change is a migration file in version control, applied in order. No manual edits to any shared environment, ever.
- Never edit an applied migration — migrations are append-only history; write a new one.
- Roll forward, not back: down migrations are a local convenience, not a production plan.
- Migrations contain raw SQL or the migration DSL only — never app model imports (they drift).

## Zero-downtime changes

Expand → backfill → contract:

1. Additive first: nullable column, new table, index — all non-breaking.
2. Code writes both shapes, reads old.
3. Backfill in small batches with pauses — never one giant UPDATE.
4. Flip reads, then constrain, then drop the old shape.

- Set `lock_timeout` (1–5s) before every DDL and retry on failure — a blocked ALTER queues every query behind it and takes the site down.
- `NOT NULL` on an existing table: add nullable → backfill → `CHECK ... NOT VALID` → `VALIDATE CONSTRAINT` (light lock) → `SET NOT NULL`. Same two-step for new FKs on large tables.
- `CREATE INDEX CONCURRENTLY`, always, outside a transaction. No table rewrites or type changes on hot tables in business hours.

## Denormalization

Only after a measured problem; only read-path rollups (`vote_count`); always derivable from normalized truth; maintained in the same transaction as the source write or rebuilt by a job. A 5-person-group app essentially never needs more.

## Mistake checklist

Nullable everything · missing FK indexes · app-only uniqueness · native enums · `timestamp` without zone · float money · polymorphic FKs with no enforcement · edited applied migrations · one giant backfill · DDL without lock_timeout · soft delete everywhere
