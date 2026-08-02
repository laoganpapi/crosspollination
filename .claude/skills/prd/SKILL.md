---
name: prd
description: Write or review a product requirements document. Load when asked for a PRD, a product or feature proposal, a requirements doc, or product user stories. Covers structure, section-by-section guidance, requirement style, prioritization, and pitfalls.
---

# PRD authoring

Sources: Atlassian's agile requirements guide; Carlin Yuen's "Writing PRDs and product requirements." A PRD is a decision document — master §11 applies on top of everything below (rationale per decision, labeled decided-vs-open, observable outcomes). The writing-standards skill applies too; load both.

## What a PRD is, and is not

- A vehicle for alignment: it defines the product's purpose, features, and behavior so the team shares one understanding of what to build and why. Success test: a reader understands the priorities, the features, and the work without needing more detail.
- Built on shared understanding of the customer, not exhaustive specification. Spec'ing every detail and hoping you spec'd the right things is the failure mode agile requirements exist to avoid. State higher-level requirements; leave implementation to the people building, who can fill it in because they share the customer understanding.
- A PRD assumes a validated user need. If users or the problem are still unclear, write a strategy/exploration doc instead — do not draft a PRD to find out what the product is.
- A living, concise document, written with the team, updated as decisions land. Target 6–8 pages; shorter is better.

## Structure

Header table first: owner and participants, status, target release.

1. **Problem / opportunity.** The user or business problem, dug to the root. Never a solution restated as a problem ("user can't use X" is not a problem statement).
2. **Objectives and measurable outcomes.** 2–3 bullets defining success, tied to background and strategic fit — why this, why now, how it serves the larger goal.
3. **Target users and use cases.** Specific users. Alignment here keeps development matched to positioning.
4. **Assumptions.** What is being taken as true — technical, business, and user assumptions the plan rests on.
5. **Current journeys / landscape** (optional). How users cope today, existing solutions. Link out to detail; do not embed it.
6. **Proposed solution / elevator pitch.** 2–3 lines in plain language. For a product: the top 3 MVP value propositions and a conceptual model diagram.
7. **Requirements / user stories.** The core — see requirement style below.
8. **User interaction and design.** Links to design explorations and wireframes per story, added as the solution firms up.
9. **Questions.** A live table of things still to decide or research — this is the §11 Open list; readers ask here instead of inventing.
10. **What we're not doing.** Explicit out-of-scope items, including deferred-not-rejected ones, so focus holds.
11. **Appendix.** Links only: UX detail, design decisions, go-to-market, competitive analysis.

## Requirement style

Do:
- Default to the minimum: the fewest requirements that test the idea. Leave everything unproven out — the Open list and later versions are where additions get decided.
- State functionality from the user's or business's side: "First-time user must accept the privacy policy to use the product."
- Include telemetry requirements: "Product team can monitor and visualize user engagement."
- Mark priority on every requirement: [P0] adoption-critical, [P1] adds meaningful value, [P2] nice-to-have.
- Bucket by use case or user journey, not chronology, so each journey reads end-to-end.
- Cover the critical user journeys: creation, first-time use, maintenance, retirement, navigating at scale, and transitions into/out of the product.
- Link to sketches or UX for fast visualization.

Don't:
- Write performance mandates ("99.99% uptime", "loads within 500ms") without concrete evidence adoption requires them.
- Write design or implementation into requirements ("a welcome modal with a blue Continue button if there's no entry in the database" — all of that belongs to design and engineering).
- Plan more than 3 phases or milestones — circumstances shift before later phases arrive.

## Pitfalls

- Churn: rewriting the PRD every time design or engineering makes a call. Written right, the stable sections — problem, users, landscape, goals, functional requirements — don't change on a whim; only priorities and the appendix should move.
- Comment threads litigating implementation detail inside the PRD. Move those to the owning team's space; the PRD records the decision and the why (§11.1).
- Length nobody reads. Cut before adding; a longer document in the same style fixes nothing (§11).
