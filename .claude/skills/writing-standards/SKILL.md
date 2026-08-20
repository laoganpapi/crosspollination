---
name: writing-standards
description: Alex's prose and document conventions. Load before drafting any prose deliverable — any answer delivered as a file, or any in-chat prose answer over 300 words. Covers the full banned vocabulary list, tone, document formatting (.docx, .md, filenames), and the required structure for decision documents and handoffs.
---

# Writing standards

Deployed copy of master §2, §7, and §11 (the master at `memory/rules.md` in the home repo) — one of its two sanctioned copies. Never edit here; amend the master and regenerate (master §10).

Load this skill before drafting any prose deliverable: any answer delivered as a file, or any in-chat prose answer over 300 words. Do not draft from memory of the conventions (§7.1).

## Banned vocabulary (master §2)

Applies to every word Claude chooses: prose, chat, code comments, commit messages, filenames. Exempt: verbatim quotes from sources, ledger-faithful proper names and figures, and pre-existing identifiers, filenames, and titles being referenced — the ban governs words Claude writes, not words Claude carries. Where the checker cannot tell a carried term from a chosen one, mark it in the file with `<!-- predelivery-allow: term -->`. When in doubt about an unlisted word that smells like these, avoid it.

**Order of work (master §2).** This list governs delivered text, not drafting. Sweep the finished draft against it as part of the pre-delivery check (item 4 below); never compose against it. Writing around a hundred words is itself a source of the flat, over-careful prose item 9 bans, so holding the list in mind while drafting costs more than it saves. Decide shape first (items 6–9), repair words after. Where the two pull against each other, shape wins: a vivid sentence carrying a listed word is fixed by swapping the word, never by flattening the sentence. A banned word that reaches Alex is a degradation signal; one caught in the sweep is not — that is the sweep working.

### Banned outright, no exempt sense

unleash, spearhead, facilitate, revolutionize, holistic, cutting-edge, innovative, multifaceted, meticulous, commendable, invaluable, paramount, unwavering, unparalleled, ever-evolving, game-changer, game-changing, intricate, realm, treasure trove, myriad, plethora

### Banned, with the replacement to reach for

- delve — use examine, dig into, look at
- utilize — use "use"
- enhance — improve, sharpen, speed up; name the actual change
- crucial — name the consequence of getting it wrong instead
- deep-dive (noun or verb) — analysis, detailed look
- embark — almost always precedes "journey"; just start the thing
- vibrant, bustling, nestled — travel-writing tells; describe what is actually there

### Banned in the tell sense; fine in the literal or technical sense

- leverage — banned as verb; fine as a noun (financial leverage, mechanical leverage)
- harness — banned as verb ("harness the power of"); fine as noun (test harness, horse harness)
- foster — banned as fuzzy verb ("foster innovation"); fine for literal foster care
- elevate — banned metaphorically; fine for literal raising
- unlock — banned metaphorically ("unlock potential"); fine for literal locks and flag-gated features
- underscore — banned as emphasis verb; fine as the _ character
- showcase — banned as verb; fine as a literal noun (a product showcase)
- navigate — banned metaphorically ("navigate the complexities"); fine for literal wayfinding and UI navigation
- resonate — banned metaphorically; fine in acoustics and physics
- boast — banned as feature-listing verb ("boasts three pools"); fine for actual bragging
- robust — banned as generic praise; fine in technical senses with specifics (robust to outliers)
- comprehensive — banned as self-praise of output; fine when literally claiming completeness and meaning it
- dynamic — banned as praise ("dynamic team"); fine in technical senses (dynamic typing, dynamic loading)
- tapestry — banned metaphorically ("rich tapestry of cultures"); fine for actual textiles
- landscape — banned as metaphor ("the AI landscape"); fine for literal terrain and landscape orientation
- journey — banned as metaphor ("your learning journey"); fine for literal travel
- testament — banned inside "a testament to"; fine in the legal and biblical senses
- beacon — banned metaphorically ("a beacon of hope"); fine for literal beacons and web beacons
- symphony — banned as metaphor ("a symphony of flavors"); fine for actual music
- streamline — banned as corporate verb; fine in fluid dynamics and literal aerodynamic shaping
- seamless — banned as praise; fine in manufacturing senses (seamless pipe, seamless garment)
- supercharge — banned metaphorically; fine for literal superchargers and engines
- synergy — banned as business praise; fine as the pharmacology term (drug synergy)
- pivotal — banned as generic emphasis; fine in the clinical term of art (pivotal trial)
- transformative — banned as praise; fine as the copyright term of art (transformative use)
- empower — banned as motivational verb; fine in statutory drafting ("the statute empowers the agency")
- bolster — banned as generic verb; fine as the literal noun and the evidence-law term (improper bolstering)

### Banned as sentence-opening transitions

furthermore, moreover, additionally — restructure or just start the sentence. Mid-sentence "also" is fine.

### Banned phrases and constructions

- "it's important to note that" / "it is worth noting that" / "it's worth mentioning" — delete the throat-clearing, state the point
- "in today's fast-paced world" / "in today's digital age"
- "in the ever-evolving landscape of X"
- the empty-contrast construction: "It's not about X, it's about Y", "This isn't X. It's Y." — banned where one half carries no distinct content. Contrasts where both halves carry distinct factual content are fine, especially causal corrections ("fails not because the mock is wrong but because the fixture is stale")
- "serves as / stands as / is a testament to"
- "plays a pivotal role in" / "plays a crucial role in"
- "at the end of the day"
- "let's dive in" / "let's explore" / "without further ado"
- "dive deeper into"
- "great question" / "excellent point" — any praise of the prompt before answering
- "I hope this helps" — and every closing service sign-off
- "when it comes to X" — restructure the sentence around the actual subject
- "in conclusion" / "in summary" / "ultimately" opening a closing paragraph
- thesis-restatement closer: a final paragraph re-summarizing the piece — end on the last substantive point instead
- rhetorical-question opener: "Ever wondered why...?", "What if I told you...?" — open with the claim
- "in a world where..." — the movie-trailer opener
- "whether you're a seasoned X or just starting out" — the fake-inclusive audience straddle
- "look no further"
- "unlock the power of" / "unlock the potential of"
- "take your X to the next level"
- "a rich tapestry of"
- "navigate the complexities of"
- "here's the kicker" / "here's the thing" — manufactured pivot
- "the world of X" / "in the world of X" as topic framing
- "hidden gem"
- forced rule-of-three: triadic lists ("faster, smarter, better") and the staccato "No X. No Y. Just Z." pattern where two items or one would do
- false-range construction: "from X to Y" spans that are not a real continuum ("from ancient temples to bustling markets")
- "the key takeaway is"
- em-dash contrast tic: repeated "X — not Y — Z" interjections and "It's not X — it's Y" sentences; at most one em-dash aside per response, or per ~500 words in a document
- hedge-opener padding: "generally speaking", "it is important to consider", "while it is true that" — commit to the claim or cut it
- decision handed back in prose (§1.3b): "next is yours", "your call", "up to you", "let me know which", "say the word", "I'd take X first", "which do you want" — a turn ending on a decision ends on a picker, never on a sentence inviting Alex to choose
- litotes — stating a thing by denying its opposite: "not bad", "not without merit", "no small feat", "not uncommon". Say the thing: "good", "useful", "a real achievement", "common"
- irony and sarcasm — writing the opposite of what is meant, or deadpan understatement for effect. State the actual assessment, plainly

## Decision documents and handoffs (master §11)

Applies to any deliverable whose readers act on the decisions it records — specs, story documents, plans, briefs handed to agents or collaborators. Missing information here is a kinds problem, not a volume problem: a longer document in the same style fixes nothing.

1. Carry the why. Every recorded decision states, in 1–2 sentences, what was rejected and what the decision protects — rationale is what lets a reader resolve micro-decisions the document does not cover. Highest-value field in the document.
2. Observable done. Completion criteria are statements an outside checker could verify — what a finished version demonstrably does, not what exists. If no failing test could be written against a criterion, rewrite it until one could.
3. Mark epistemic status. Decided ("ratified — do not relitigate") and undecided ("open — ask before building") are labeled explicitly. An Open list is mandatory so readers ask instead of invent.
4. States and events. Anything with a lifecycle gets its states, transition triggers, and the event recorded per transition enumerated. When downstream work depends on an event log from day one, this cannot be deferred.
5. Own knowledge only. Never fill downstream gaps (data models, API shapes, implementation) with guesses — a guess in a handoff gets read as a decision. Gaps go to the Open list.
6. Edge rulings. Record the awkward cases actually discussed and how each was ruled — cheap now, unrecoverable later.
7. Per-unit format when producing a handoff: Decision / Why / Done when (2–5 observable statements) / States & events / Edge rulings / Open / Out of scope.
8. Ratification loop. Reader-side drafts of done-when and states-and-events come back for yes/no ratification — an interview loop, not a writing assignment.

9. The reading sits beside the evidence. Every table, chart or figure block carries one line saying what it means for the decision, and that line states something the cells do not — a comparison, a threshold crossed, a consequence. A bare exhibit hands the analysis back to a reader who has neither the model nor the time. This is not the scaffolding master §7.10 bans: scaffolding restates what was just said, and this says what the numbers will not.
10. Each option carries its success conditions and the failure mirroring each. State what has to hold for an option to work and, against each condition, the way it fails. A cost is what an option charges; a failure condition is what makes it the wrong choice, and neither implies the other.
11. Precedent carries the part that cuts against it. A case cited in support of an option gives its outcome whole, the half that argues against it included, and says in one line what it establishes. Half a case is advocacy, and a reader who already knows the case stops believing the document there.
12. Test the recommendation to destruction and name the breaking point. Recompute it at reduced achievement and give the level at which it stops holding as a number. Name the scenario that fails and the direction it fails in — one that breaks opposite to the risk everyone is watching is itself the finding. Say what the recommendation does not fix.
13. Say when the question is aimed at the wrong variable. Where the thing being decided moves the outcome less than something outside the question, both quantities go in the opening summary, and the section establishing it says which findings outrank the answer asked for. Not scope expansion (master §1.2): the deliverable stays what was asked and carries the finding inside it.
14. Anchor the unit before the figures. Where numbers live in a unit the reader does not think in, open with the conversion into one they do, sized on a quantity they already recognise. State the construction rule once, in the reference note, and every figure downstream inherits it.
15. Size the demand a figure assumes. Any projected quantity that needs somebody else to supply something — buyers, headcount, throughput, budget — is printed beside the observed size of that capacity, with its source. A number that needs the world to be ten times its measured size is a finding, not a projection.
16. Open items name their owner and what makes the deadline. Every entry on the Open list says who decides it, by when, and what fixes that date — the event that closes the option, not a preference. An open item with no owner is a question nobody answers.
17. A proposal says what rests on it. Anything offered as an option rather than used as an input states whether any other figure depends on it, so a reader who rejects it can tell how much of the analysis they have just lost.

## Document forms

Long-form deliverables with a settled shape have their form recorded separately, loaded only
when writing one:

- Investment memo, diligence pack, company brief — [references/memo-form.md](references/memo-form.md)

## Formatting (master §7)

1. Produce the asked format exactly. "Make a doc" means the repo's declared working format (its CLAUDE.md context line) unless another format is named.
2. .docx deliverables: Helvetica throughout; tables without banding — no alternating row shading.
3. Filenames: a name Alex states wins verbatim. When naming is left to Claude, deliverable filenames are date-prefixed in "M D YY" form, no leading zeros: `5 12 26 claude.md`, `12 3 26 brief.docx`. Repo infrastructure files (CLAUDE.md, ledger.md, memory-graph files, skills, installers, READMEs) are never date-prefixed. A node has no filename of its own — it is a heading inside its domain's file (master §6.1) — so nothing here applies to one.
4. Pre-delivery check, every deliverable, in this order (master §7.5): shape first — the form fits the content (item 7), headings are noun phrases (item 6), rhythm and weighting vary (item 9); then the §2 vocabulary sweep over the finished draft; then format and filename match the ask; scope matches the ask — one deliverable, no bonus formats; every material fact checked against the ledger (master §3); every sensitive commitment a marked quote with citation (master §4). End on the last substantive point — no summary paragraph, no sign-off, no offer of further help inside the deliverable (an adjacency offer goes in chat, after it).
5. Minimal by default (master §7.6). Designs, PRDs, and proposals start from the smallest version that tests the idea — fewest features, screens, and states — so what to add next is a decision made on evidence, not a pruning job. Untested features in a first version are defects. Pages themselves stay plain: no decorative bold, no dense nesting, no visual noise.
6. Headings are noun phrases (master §7.7). "Exit conditions", not "How to set exit conditions". No verbs, no questions, no sentences. This holds for slide titles. Two forms are banned outright, both of which pass as noun phrases and should not:
   - A heading ending in a comma plus a past participle: "Seven avenues, ranked", "The options, compared", "The model, explained". It reads as a verdict while deleting who judged and on what basis. State the claim in full — "Seven financings, ordered by where tokenising changes most" — or drop it.
   - A kicker: a second heading stacked above the heading. Allowed only when it carries what the heading does not, such as a number or a section name. A label that restates the heading at a smaller size is two headings and one idea.
7. Structure over prose (master §7.8). Content with parts, steps, states, or comparisons never arrives as prose. Pick the form by what the content is:
   - **Relationships between parts** — flow, dependency, states, hierarchy, what feeds what, what can follow what — get a **diagram**.
   - **Items compared on shared attributes** get a **table**.
   - **Anything else with parts** gets a **list**.
   A table standing in for a diagram is the usual miss: it flattens a relationship into rows and loses the thing worth seeing. Paragraphs run two or three sentences, only for reasoning that is genuinely continuous; a list item counts as a paragraph.
8. Diagram form (master §7.9). Diagrams are drawn with characters inside a code block, which renders anywhere — chat, file, terminal, print. Diagram markup a reader's client may not render (mermaid and the like) belongs in published pages and repository files only. In chat it arrives as raw source, which is worse than no diagram at all.
9. Shape is the tell (master §7.10). Four habits mark text as machine-made, and no word list catches any of them:
   - Every sentence landing at the same middling length, with no short one set against a long one.
   - Every list running to three, every section to the same size.
   - The load-bearing point given the same space as the incidental one.
   - Scaffolding: restating the question, signposting what is coming, summarising what just closed.
   Vary the rhythm, let length signal what matters, cut the scaffolding. Nothing mechanical checks this, so it falls to the writer on every pass.
10. Lists hidden in sentences (master §7.8, testable form). Four or more parallel items in a comma-series is a list wearing a disguise — break it out where the items are things a reader may need to find again, compare, or count. This is the most common way a document that reads well still fails: the prose is fine sentence by sentence, and the reader cannot scan, count, or find one item again. A short series naming categories in passing is not caught by this. The one test with no judgement in it: parallel items that each begin with a repeating `Label:` — a date, a name, a category — are already a list, and only the line breaks are missing.
11. Enumerated sections take the labelled-bullet shape (master §7.8, testable form). Any section whose job is to enumerate — risks, options, competitors, failure modes, requirements — runs one bullet per item as **name** → mechanism → consequence: what it is, why it happens, what it does to the reader's decision. Never a bare label with no mechanism, never a mechanism with no consequence. A section written this way is the standard the rest of the document is held to; if one section earns bullets, the enumerating sections beside it have not earned prose.
12. A document never vouches for its own quality (master §7.11). No deliverable describes itself as rigorous, thorough, comprehensive, carefully checked or written in plain words. The claim buys the reader nothing: the reader is holding the thing itself, and the pass that writes the claim is the pass that did not do it. A sentence promising every term is explained on first use gets written into a document whose terms are not. Master §12.4 is the same rule for code, where "it should work" is never a delivery.
    Carry the record instead: what was run, what was compared against what, what was not verified, and how much of each. It goes where the document already has a place for it, as a method line, a scope note, or a caveat beside the figure. Never a new appendix or a compliance section, which is the scope master §1.2 and §7.6 both refuse.
    The test: no sentence asserts that the document is good. What survives names an act and a count the reader can check against the page: "every total recomputed from its printed rows", "three of eleven prices unverified", "figures from the filing, not the summary page".


<!-- Propagation stamps, checked by rules/propagate.py (master §10.1). The §2 vocabulary blocks are checked by exact set equality instead and need no stamp. A stale hash does not mean this file is wrong; it means nobody has re-checked it since the master moved. -->
<!-- from: master §7.1 sha:22a4bbc7 -->
<!-- from: master §7.2 sha:b06f1779 -->
<!-- from: master §7.3 sha:7d780b4d -->
<!-- from: master §7.4 sha:6af9b438 -->
<!-- from: master §7.5 sha:39c2210e -->
<!-- from: master §7.6 sha:7f5686da -->
<!-- from: master §7.7 sha:87d75732 -->
<!-- from: master §7.8 sha:f195ed7b -->
<!-- from: master §7.9 sha:d75978af -->
<!-- from: master §7.10 sha:3ac3bdab -->
<!-- from: master §7.11 sha:5b187b35 -->
<!-- from: master §11 sha:29634162 -->

<!-- copy sha:9c4b7af8 words:3392 -->
