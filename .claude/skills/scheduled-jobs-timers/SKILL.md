---
name: scheduled-jobs-timers
description: Deadlines, expiries, and scheduled work — sweep vs delayed jobs, idempotent handlers, cancellation by state, missed-fire recovery, time testing. Load when the task involves anything that happens at or after a point in time — T+24h actions, invite expiry, escalation timers, reminders, recurring jobs. Not for state-machine design itself or notification content.
---

# Scheduled jobs and timers

## The load-bearing rule

The database row is the source of truth; the scheduler is only an alarm clock.

- Every deadline lives on the domain row: `expires_at`, `decide_by`, `extension_count`, `status`. The timer merely says "look now"; the handler re-reads the row and acts only if the condition still holds in the database. Stale, duplicate, early, and late fires all become harmless.
- Reads don't trust the timer either: "is this invite valid" compares `expires_at < now()` directly. A thing is expired the instant its timestamp passes, whether or not the cleanup job ran. Enforcement in queries; processing (transitions, notifications) in jobs.

## Mechanism choice

| Mechanism | Fits | Notes |
|---|---|---|
| Cron sweep every minute | Invite expiry, T+24h actions, minute-level tolerance | The default answer at small scale — one moving part, self-healing, nothing to cancel |
| Delayed job (queue) | Second-level precision, per-item fan-out | Must still re-check the DB at fire time |
| Durable execution engines | Long multi-step sagas | Know they exist; don't reach first |

- Sweep query: `SELECT … WHERE deadline_at <= now() AND status='pending' FOR UPDATE SKIP LOCKED`, with a partial index on `(status, deadline_at)`.
- Prefer a Postgres-backed queue over a separate broker: the job enqueues in the same transaction as the business write, killing the row-committed-but-job-lost bug class.

## Idempotency

The timer will fire twice. Exactly-once delivery is a lie; exactly-once effect = at-least-once delivery + idempotent handler.

1. Load the row
2. Check the precondition (`status='pending' AND deadline_at <= now()`)
3. Transition via guarded update (`… WHERE id=$1 AND status='pending'`)
4. Zero rows affected → exit silently; someone else did it

- Side effects that leave the database (email, webhook) get a deterministic dedup key (`decision:{id}:reminder:24h`) with a unique constraint, inserted in the same transaction as the transition.
- Commit the state change before sending the email — crash between send and commit means duplicate email forever.

## Cancellation and ladders

- With a sweep there is nothing to cancel: the vote arrives, status flips, the WHERE clause stops matching. This is the sweep's biggest win.
- With queued jobs, never hunt down and delete the job — let it fire and no-op against current state. Carry the expected `deadline_at` in the payload as a fencing token; if it differs from the row, exit.
- Extension caps live in data (`extension_count` with a CHECK constraint), enforced at write time, never inside the timer.

## Clocks

- UTC everywhere; `timestamptz` columns; compare against the database's `now()` — one clock to trust.
- Never add intervals in app code with naive datetimes; DST bugs live there. Store IANA zone names for local-time rules, never offsets.

## Missed fires

- The sweep is the recovery mechanism: `<= now()` with no lower bound drains any backlog after downtime.
- Queue-based timers get a reconciliation sweep anyway (hourly: pending rows past deadline with no completed action) — alert if it ever finds work.

## Testing

- Inject or freeze the clock; never sleep.
- Core set: fires once → transition; fires twice → no-op; state changed before fire → no-op; restart with overdue rows → sweep catches them; deadline extended → old timer harmless; boundary at exactly `deadline_at`; a 24h window crossing a DST change.
