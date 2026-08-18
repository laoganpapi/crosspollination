---
name: backend-testing-strategy
description: Test-first backend development — suite shape, mocking boundaries, real-database tests, clock control, flake prevention. Load when writing or reviewing backend tests, setting up a test suite, or enforcing test-first flow on agent-written code. Not for frontend/UI testing or CI pipeline configuration.
---

# Backend testing strategy

## Test-first flow

1. State the behavior as an observable outcome in domain language: "an invite accepted after `expires_at` returns 409 and stays expired" — never "the helper returns true".
2. Write the test against the public API (endpoint or service function), then run it.
   - Read the failure: it must fail on the behavior assertion, not a compile error.
   - A test that passes immediately tests nothing. Stop and fix it.
3. Minimum code to green. Refactor with tests untouched.
4. Agent guardrails — this is where agents cheat: never delete or weaken a failing test to reach green; after green, re-check the test still asserts the original behavior, not whatever the code happens to do. Tests written after code by the same agent merely notarize its bugs.

## Suite shape

| Layer | Share | Content |
|---|---|---|
| Static (types, linters) | free | Whole bug classes eliminated, doubly valuable on agent code |
| Unit | small | Real logic only: transition matrices, guard boundaries, pure calculations — no doubles at all |
| Integration | the bulk | Request in → assert response, database state, and emitted events. Real DB, real wiring |
| End-to-end | a handful | Smoke flows only (invite → accept → task → review → escalation) |

The weight sits at integration because tests resembling real use give the most confidence per test.

## Mocking boundary

- Test units of behavior, not units of class. Never test private methods or internal call sequences.
- Mock only unmanaged dependencies — external things whose interactions are observable from outside: email providers, third-party APIs, outbound webhooks.
- The database is a managed dependency: use the real thing. Mocking your own repository couples tests to implementation — they break on refactor and pass on bugs.
- Acceptance test for the suite: a behavior-preserving refactor breaks zero tests. If it breaks tests, the tests were wrong.

## Clock control

- Ban direct `now()` in domain code; inject a clock, enforced by a lint rule. Deadline and expiry logic is untestable against the wall clock.
- Tests read: create invite expiring in 48h → advance clock 49h → run the sweep → assert `expired` and the emitted event. Deterministic and fast.
- Timer jobs are tested by invoking the job function directly with the clock set — never by sleeping or waiting on a real scheduler.

## Database tests

- Real engine, same version as production, per suite (containerized). Constraints, transaction semantics, and SQL errors are exactly what mocks structurally cannot catch.
- Isolation per test: transaction rollback or truncate — never shared mutable rows.
- Migrations run in the suite. One test replays the full event log into every projection — schema-compat regression for free.
- Contracts: provider-side schema validation (OpenAPI checked against the running app) suffices for one team; emitted events are contracts too — validate their shape.

## Flake prevention

- Design out the causes: real sleeps, shared state, real time, real network, order dependence, unbounded eventually-consistent assertions.
- Every test runs alone and in random order. Zero sleeps. A flake is quarantined and fixed the day it appears, never retried into oblivion.

## Coverage and limits

- Don't test framework behavior, trivial mappers, private internals, exact log strings, or mock round-trips.
- Coverage is a signal, not a target — never set a number an agent can satisfy with assertion-free tests. The sharper check: break the behavior and confirm its test goes red.
