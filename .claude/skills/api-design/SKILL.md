---
name: api-design
description: HTTP API design — resource naming, status codes and error bodies, cursor pagination, idempotency keys, versioning stance, boundary validation. Load when designing or reviewing REST endpoints, error formats, or API contracts. Not for GraphQL, RPC frameworks, or internal function interfaces.
---

# API design

## Resources and URLs

- Nouns, plural, lowercase: `/projects/{id}/tasks/{id}`. Nesting two levels max; deeper relationships become query filters (`/tasks?project_id=…`).
- No verbs in paths. A genuine state transition that doesn't map to CRUD gets a sparing custom action: `POST /invites/{id}/revoke` — one per real transition, not a habit.
- GET list, POST create, GET fetch, PATCH partial update (preferred over PUT), DELETE remove. GET and DELETE never take a body.
- Paths identify; query params filter, sort (`?sort=-created_at`), paginate.

## Status codes and errors

- The small honest set: 200, 201 + Location, 202 (async accepted), 204 (delete), 400 (validation), 401, 403, 404 (also for hiding existence), 409 (state conflict), 429 + Retry-After, 500.
- One error format for the whole API — RFC 9457 `application/problem+json`: `type` (URI doubling as doc link), `title`, `status`, `detail`, `instance`, plus an `errors` array for field-level validation (`{field, code, message}`).
- Never 200-with-error-body. Never leak stack traces, SQL, or internal class names.
- Return all validation failures in one response, not first-failure.

## Pagination

- Cursor, not offset: offset skips or duplicates rows under concurrent writes and forces scan-and-discard. The cursor is an opaque base64 token over the last-seen sort key `(created_at, id)` — clients must not parse it.
- Shape: `{data: [...], next_cursor: "…" | null}`; null is the only end signal. `limit` with a default (20–50) and hard cap.
- Every list endpoint paginates from day one — retrofitting is a breaking change.

## Idempotency

- Unsafe-but-retryable POSTs accept an `Idempotency-Key` header (client UUID). Store key → first response and replay it within a window; same key with a different body → 409, never a replay.
- Persist the key in the same transaction as the created row, under a unique constraint, so a race can't double-create.

## Versioning stance

- `/v1` in the path from day one; never use the escape hatch until forced.
- Additive-only: new optional fields, new endpoints, documented-open enums. Never rename, retype, remove, tighten, or change status codes on existing behavior. Clients tolerate unknown fields — say so in the docs.
- When a break is unavoidable, per-field deprecation with a sunset window beats a version fork.

## Boundary validation

- Validate at the edge against the schema before any business logic: types, required fields, enum membership, lengths, formats.
- The request/response DTO is a separate type from the database model. Serializing ORM entities leaks columns you'll be stuck supporting.
- Unknown fields: reject or explicitly ignore — pick one, document it.

## Conventions

| Element | Rule |
|---|---|
| Timestamps | ISO-8601 UTC (`2026-08-06T14:03:00Z`), fields named `*_at`, on every resource |
| IDs | Opaque strings to clients; prefixed ids (`task_8f3k…`) make logs self-describing |
| Casing | One of snake_case or camelCase, never mixed |
| Booleans | Phrased positively (`is_archived`) |
| Money | Integer minor units + currency code, never floats |

## Contract

- OpenAPI in the repo, reviewed like code, generated from the same schemas that validate requests so it can't drift. Breaking-change lint in CI.

## Mistake checklist

Verbs in URLs · 200 with `{"error": …}` · offset pagination · unpaginated lists · ORM models on the wire · three error formats · local-time timestamps · POST retries double-creating · breaking changes shipped as minor
