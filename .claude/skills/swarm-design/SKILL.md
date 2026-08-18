---
name: swarm-design
description: Decomposing work across multiple agents — when a swarm beats one agent, orchestrator-worker structure, self-contained briefs, file handoffs, judge bias mitigation, adversarial verification, red-team rounds. Load when designing a multi-agent pipeline, research fan-out, or review swarm. Not for the loop mechanics of a single unattended run (harness-design).
---

# Swarm design

## The decision first

| Work shape | Winner | Why |
|---|---|---|
| Read-heavy, parallelizable — breadth research, independent perspectives, more material than one context holds | Swarm | Each agent gets its own context window and compresses independently |
| Write-heavy, dependent — sequential edits to shared artifacts, step N constraining step N+1 | One agent | Parallel writers make implicit conflicting decisions; reconciliation costs more than parallelism saves |

Reads parallelize; writes don't. When in doubt, single-threaded — it's the cheaper failure.

Cost honesty before launching: a single agent burns ~4x the tokens of chat; a swarm ~15x. Token spend explains most of the performance gain — a swarm works largely by buying more compute. Reserve it for tasks whose value covers the bill.

## Orchestrator-worker

- One lead agent owns the plan and the synthesis: decomposes, spawns workers, collects, decides whether more is needed.
- Workers never coordinate peer-to-peer; all state flows through the orchestrator.
- The orchestrator plans visibly before spawning — unplanned fan-out is where budgets die.

## Decomposition rules

- One job per agent. A brief covering two questions gets two half-answers — the same rule as one job per skill.
- Every brief carries an output contract: objective, exact output format, source guidance, and boundaries (what not to do, what other agents cover). Vague briefs are the primary cause of duplicated and misdirected work.
- Effort scales by explicit rule, not agent judgement: a fact-find gets 1 agent and a few tool calls; a comparison 2–4 agents; deep research 10+ with divided territory. Put the numbers in the orchestrator prompt or agents spawn fifty workers for a trivial question.

## Self-contained briefs

Workers share no context with the parent — no history, no prior findings. Anything not in the brief does not exist for the worker. Each brief carries its own background, definitions, constraints, and destination for output.

## File handoffs

- Stages communicate through structured artifacts with agreed names — `03_findings_supply.md`, JSON with a fixed shape — never prose relayed through the orchestrator's memory.
- Files as interfaces survive orchestrator context pressure, make runs resumable and auditable, and let a human inspect mid-pipeline. The wikiclaws pipeline (numbered prompt and output files, synthesis reading them all) is the working pattern.

## Judges and their biases

Scoring judges are usable but measurably biased: position (first slot favored, 10–15 points), verbosity (15–30 points toward longer), self-preference (toward the judge's own model family). Mitigations:

- Score against an explicit rubric of independently scored criteria, never one overall preference score — per-criterion scoring also starves verbosity bias
- Pairwise comparisons run in both orders; disagreement between orders is a tie
- Different model family for judge and generator where self-preference matters
- Periodic human spot-checks

## Adversarial verification

- A separate agent prompted to refute — check citations, hunt counter-evidence, attack reasoning — catches what a scoring judge rubber-stamps. "Find the flaw" and "grade this" elicit different behavior.
- Track the kill rate: near-zero means the red team is soft, not that the work is clean.
- Red-team rounds run after synthesis, and findings are adjudicated — each accepted or rejected with reasons — before any revision. Revising straight from raw red-team output lets bad objections mangle good work.

## Failure modes

Duplicated work (vague briefs — fix with boundaries) · two agents writing one artifact (partition or serialize) · unbounded fan-out (hard caps) · judge rubber-stamping (adversarial framing plus kill-rate) · synthesis dropping minority findings (require dissents listed, not just consensus) · orchestrator overflow on long runs (summarize finished phases to files, spawn fresh workers)
