---
name: scenario-sensitivity
description: Structure scenarios, sensitivity tables, and uncertainty analysis on an existing model. Load when the task involves base/upside/downside cases, testing which assumptions move the answer, building data tables, tornado charts, or deciding whether simulation is warranted. Assumes a model already exists.
---

# Scenario and sensitivity analysis

## Scenario architecture

- One switch cell drives every scenario; no scenario is built by editing inputs in place
- Each scenario is a full column of assumptions on the drivers sheet, selected by `INDEX` or `CHOOSE` against the switch
- Three named cases is the working default: base, downside, upside. More than five is a signal the drivers were never narrowed
- Every case needs a one-line story of what has to be true in the world for it to happen — a case without a narrative is a number nobody can defend

## Flex variables

- Sensitize the two or three inputs that actually move the answer, not every input
- Find them first: move each driver by the same relative amount and rank the output changes (a tornado)
- Inputs with negligible impact get fixed and stated as fixed — that is a finding worth reporting
- Flex ranges come from evidence — historical variance, comparable benchmarks, contract terms — not from round numbers

## Table types

| Form | Use |
|---|---|
| One-variable table | One driver against one or more outputs |
| Two-variable table | The two dominant drivers, output in the corner |
| Tornado | Ranking impact across many drivers |
| Break-even solve | The input value at which the decision flips |

- The break-even is often the most useful single output: "this works unless churn exceeds 4.2% monthly" beats any range

## Simulation

- Monte Carlo is justified only when input *distributions* are genuinely known and interactions are non-linear
- With guessed distributions it produces false precision — a wide, confidently-shaped output built on invented inputs
- When used: state the distribution and source for each input, the correlation assumptions, and the iteration count
- Report percentiles, never a mean alone

## Presentation

- Lead with the break-even or the range, not the base case
- State which assumptions the conclusion survives and which kill it
- A sensitivity that shows the answer never changes is a real result — report it plainly rather than manufacturing spread

## Checks

- Every scenario recalculates end to end when the switch changes — verify by toggling and watching the output move
- No orphaned cells still pointing at the old base case
- Scenario labels appear on every output so a printed page is never ambiguous
