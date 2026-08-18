---
name: harness-design
description: Designing runs that repeat or continue unattended — checkable exit conditions, failure exits, checkpointing, fresh context per pass, verification gates, run reports. Load when building a loop, an overnight run, a retry-toward-goal system, or any harness an agent runs inside. Not for decomposing work across multiple agents (swarm-design) or one-pass pipelines.
---

# Harness design

## Definition

The deterministic scaffolding around a nondeterministic agent. The agent decides how; the harness decides whether to keep going, what state survives, and what counts as done. Infinite loops, false completions, lost work, and runaway cost are harness gaps, not model gaps.

## Exit conditions (master §13)

- The success exit is observable state the loop checks mechanically each pass: all tests pass, a validation script returns 0, every checklist item marked done. Never "the output looks good" — a judgement call the agent will rubber-stamp.
- If the goal can't be phrased as a checkable test before the run starts, make it checkable (write the tests, the checklist, the acceptance script) — or conclude a loop is the wrong tool. Interview Alex until it's testable; never start on a guess.

## The second exit

Every loop carries a failure exit alongside success:

| Exit | Example |
|---|---|
| Pass cap | Stop at 25 iterations |
| No-progress rule | Two consecutive passes with no state change |
| Budget | Token or dollar ceiling |

A loop with only a success exit doesn't run until done — it runs until exhaustion, because the stuck cases (goal unreachable, flaky test, repair-break cycle) never trip success. A no-progress rule whose condition is already met fires now, without extensions.

## Checkpointing

- The agent instance is disposable; durable state lives outside it: a git commit after each verified pass (checkpoint and rollback in one), a progress file (done / next / learned), a machine-readable task list the loop reads.
- A crash or restart resumes from the last checkpoint — never from the beginning, which redoes or re-breaks finished work.
- Let the agent see failures ("this tool errored") rather than hiding them; the model adapts.

## Fresh context per pass

- Long single contexts degrade — dead ends and stale tool output crowd out the goal before the window fills.
- Each pass spawns a fresh instance fed the same standing prompt plus distilled artifacts: spec, task list with statuses, learnings file, git history.
- The distillation is the work: before a pass ends, conclusions ("auth tests need the DB seeded", "approach X failed because Y") go to the learnings file — the next pass inherits conclusions, not transcripts.
- One task per pass keeps contexts small and checkpoints clean.

## Verification gates

- False completion — the agent declaring done what isn't — is a top failure mode. Nothing counts as progress until verified by something other than the agent's claim: run the tests, run the app path, run the acceptance script, inside the loop, before the item is marked done and committed.
- A pass failing verification rolls back to the checkpoint, logs the failure to learnings, and counts toward the no-progress rule.

## Run report

Every run ends with: which exit fired · passes used · budget consumed · tasks done vs. remaining · what was verified and how · anything unverified. "Which exit fired" is the most diagnostic line — a success-exit run and a cap-exit run need entirely different follow-up.

## Cases against a loop

- The blocking state only a human can change (unreviewed PR, pending approval) — polling burns budget and cannot progress; use event delivery, say what's awaited, end the turn (§13.5)
- No checkable success condition exists or can be built (taste-based, open-ended "make it better")
- The work is one sequential pass — that's a pipeline of fixed steps, cheaper and more predictable
- Side effects aren't reversible (production writes, sends, payments) and no rollback path exists — each failed pass does damage

## Pre-launch checklist

Success predicate checkable · failure exits set · checkpointing in place · per-pass verification defined · rollback path defined · fresh-context seeding defined · report format agreed
