---
name: state-machine-modeling
description: Model backend lifecycles as explicit state machines — states, transition tables, guards, timer-driven transitions, race-safe persistence. Load when the task involves an entity with a lifecycle (invite, task, review, escalation ladder, mode), status fields, or deadline-driven transitions. Not for the event log itself or job scheduling mechanics — separate skills.
---

# State machine modeling

## Explicit states

- One `status` column per lifecycle, every value spelled out: `draft → sent → seen → accepted | declined | expired | revoked`.
- Never boolean flags (`is_sent`, `is_expired`) — n booleans create 2^n combinations, most impossible, all needing defense.
- Independent concerns are separate machines. Away mode is a machine on the user (`active ⇄ away`), consulted as a guard by other machines — never a state inside them.
- State lives in exactly one place. Timestamps and counters are evidence, never consulted to decide what state something is in.

## Transition table as the spec

Write the table before any code, and keep code shaped like the table — a map, not scattered ifs:

| from | trigger | guard | to | emits |
|---|---|---|---|---|
| sent | invitee_opened | — | seen | invite.seen |
| seen | accept | not expired | accepted | invite.accepted |
| sent, seen | timer:expiry | now ≥ expires_at | expired | invite.expired |
| pending | timer:deadline | extensions < cap | pending, deadline+Δ | review.extended |
| pending | timer:deadline | extensions ≥ cap | escalated | review.escalated |

- Guards are pure boolean functions of state, context, and trigger — no side effects.
- Caps are counters plus guards, never extra states (`escalated_once`, `escalated_twice` is state explosion).
- Entry/exit actions: schedule the expiry timer on entering `sent`; cancel on exit. That pairing kills the "timer fired for a state we left" bug class.
- Every transition emits its past-tense event. The transition is the only code path that writes status and appends the event, in one transaction.

## Illegal transitions

- Anything not in the table is rejected with a typed error → 409 to callers, and logged — illegal-transition attempts are a bug detector.
- Repeats are idempotent: `accept` on already-`accepted` returns success as a no-op. Distinguish "same trigger, already there" (no-op) from "invalid from this state" (409).

## Timer transitions

- A timer firing is a trigger row like any other, actor `system:timer`.
- The handler re-reads the row at fire time — the deadline may have moved after scheduling. Fire time is not truth; the row is truth.
- Prefer a sweep (`expire everything WHERE status IN (...) AND expires_at < now()`) over per-row scheduled jobs at small volume — one query, naturally idempotent, nothing to cancel.

## Race-safe persistence

- The core move is the guarded update: `UPDATE ... SET status='expired' WHERE id=$1 AND status IN ('sent','seen')`.
- Zero rows affected means you lost the race: reload and re-decide, or no-op — never blind-retry the same write.
- Add an optimistic `version` column when a transition writes other fields too.
- History lives in the event log; the status column answers "what now", the log answers "how did we get here".

## Exhaustive testing

- The table makes it mechanical: for every (state, trigger) pair assert the expected (to-state, event) or the typed rejection. Generate the matrix from the table itself so tests can't drift from the spec.
- Test each guard at its boundary — extensions at cap−1, cap, cap+1; expiry at t−1s, t, t+1s — with an injected clock, never the wall clock.
