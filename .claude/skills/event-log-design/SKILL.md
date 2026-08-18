---
name: event-log-design
description: Design an append-only domain event log or audit trail — event naming, payload vs envelope, versioning, projections, idempotent consumers. Load when the task involves recording domain events, building an audit trail, enumerating event names and payloads for a spec, or deciding between event sourcing and an audit table. Not for notification delivery or state-machine design — separate skills.
---

# Event log design

## Scope decision first

- Deciding question: do you need to *rebuild state* from events, or only *explain* state? Explain-only means an audit-event table, not event sourcing.
- Default for a small product: state tables stay the source of truth; an append-only event table is written in the same transaction as every state change. You keep the audit trail, timeline, and debuggability without rehydration machinery.
- Reserve true event sourcing for the one entity where "how did it get here" is the product, if anywhere.

## Event naming

- Past-tense business facts: `invite.sent`, `invite.accepted`, `review.escalated`. Format `entity.action_past_tense`, lowercase, singular entity.
- Name the business operation, never the write: `task.reassigned`, not `task.updated`.
- Two banned patterns: property sourcing (one event per field change) and CRUD sourcing (`x.created/x.updated/x.deleted`). If the event can't be named in past-tense business language, the command model is wrong.
- Event type names are stable identifiers — renaming a deployed type is a breaking change.

## Payload vs envelope

- Payload: domain facts only — what changed and the values needed to rebuild or explain state.
- Envelope, identical on every event: `event_id` (minted once — this is the dedup key), `event_type`, `event_version`, `stream_id`, per-stream `sequence`, `occurred_at` (UTC), `actor` (a timer is an actor too: `system:escalation_timer`), `correlation_id` (set once at the flow's entry, copied downstream), `causation_id` (the parent event's id).
- Rule: projections read payload; tracing and audit read envelope. `actor` never floats between the two.

## Schema evolution

- Additive-only in place: new optional fields with defaults. Never rename, retype, or remove a deployed field; never mutate stored events.
- Breaking change: new event type, or bump `event_version` with an upcaster — a pure v1→v2 function applied on read, chained so readers only see the latest shape.
- Litmus test: if the old event can't be mechanically converted to the new shape, it is a different event, not a new version.
- Tolerant readers from day one: ignore unknown fields, default missing ones.

## Append-only discipline

- Inserts only, enforced in the database (revoked grants or a trigger), not by convention.
- Corrections are compensating events (`invite.revoked`), never edits.
- Concurrency: unique index on `(stream_id, sequence)`; conflict means reload, re-decide, retry.
- One source of truth per entity — events authoritative with disposable state projections, or state authoritative with the log as audit. Pick one and write it down.

## Projections and consumers

- Read models are throwaway: rebuildable by replay. One table per screen is fine.
- Every consumer is idempotent — delivery is at-least-once everywhere. Checkpoint the last processed sequence, or upsert keyed by `event_id`.
- Ordering is guaranteed only within a stream; design projections not to need global order.
- Side effects never fire from replay: separate "project" from "react", and gate reactions behind a processed-event ledger.

## Checks

- Every event has `event_id`, `actor`, `correlation_id`
- No CRUD-named events in the catalog
- A test replays the full log into every projection — doubles as schema-compat regression
- Event names and payloads enumerated in the spec before any dependent code is written; this is the one gap that cannot be fixed later
