---
name: notifications-delivery
description: Notification systems driven by domain events — outbox pattern, recipient and preference resolution, dedup and digests, retries, channel abstraction. Load when the task involves sending notifications, emails, or in-app alerts triggered by application events. Not for marketing campaigns or the design of the domain events themselves.
---

# Notification delivery

## Event vs decision

- Domain code emits facts (`task.assigned`, `deadline.approaching`) with entity and actor ids. It never decides who gets told or how.
- The notification layer runs stages in order: recipient resolution → suppression → preference check → rendering → channel dispatch. Each stage separately testable; rules change without touching domain code.
- Day-one suppression rules: never notify the actor about their own action; drop if the recipient lost access between event and send; drop if the subject was deleted.

## Transactional outbox

- In the same transaction as the domain write, insert the pending notification row: `id, event_type, recipient, entity refs, channel, status='pending', dedupe_key, attempts, next_attempt_at`.
- Atomic commit means no lost sends (event without message) and no ghost sends (message for a rolled-back write).
- A worker drains `status='pending'` with `FOR UPDATE SKIP LOCKED` — the table is the queue; no broker needed at small scale.
- Never send from the request handler: it ties request latency to the email provider, turns provider outages into user-facing failures, and can't unsend after a rollback.

## Dedup and digests

- Delivery is at-least-once, so every send carries a dedup guard: unique `dedupe_key` (`event_id:recipient:channel`) with insert-or-ignore, and the same key passed as the provider's idempotency key — a crash between "sent" and "marked sent" can't double-email.
- Collapsing: per recipient and entity, hold a window (minutes for activity, daily for low-priority); new events merge into one pending notification ("Alex and 2 others commented").
- Classify urgency up front: security and deadline escalations bypass every window.
- Escalation timers emit the same kind of domain event into the same pipeline — never a second path.

## Retries and failure

- Exponential backoff with jitter, capped attempts (~5); track `attempts`, `next_attempt_at`, `last_error` on the row.
- Error classes differ: provider 4xx (bad address, suppressed recipient) is permanent — mark failed, record why, stop; 5xx and timeouts are transient — retry. Hard bounces mark the address undeliverable.
- Exhausted retries land in a queryable `dead` status with an alert on its count — never silent disappearance.

## Channels

- One `deliver(notification) → result` interface per channel. In-app first (cheapest, safest default), email second, push later — upstream stages untouched.
- In-app notifications are rows with `read_at`; the unread count is a query, not a counter to keep synchronized.

## Preferences

- Stored as (user, category, channel) → enabled, defaults plus an explicit override table — absence means default, so new categories need no backfill.
- Checked at send time, not enqueue time — they can change inside a digest window.
- Every email carries one-click unsubscribe working without login. Transactional and security mail is exempt; anything marketing-adjacent is not — tag each category.

## Mistake checklist

Sending inside request handlers · event and notification in separate transactions · no dedup key so retries double-send · notifying the actor about themselves · one code path per feature instead of one pipeline · retrying permanent failures forever · preferences checked at enqueue · no dead-letter visibility · security alerts sitting in a daily digest
