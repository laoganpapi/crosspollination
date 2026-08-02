---
name: writing-standards
description: Alex's prose and document conventions. Load before drafting any prose deliverable — any answer delivered as a file, or any in-chat prose answer over 300 words. Covers the full banned vocabulary list, tone, document formatting (.docx, .md, filenames), and the required structure for decision documents and handoffs.
---

# Writing standards

Deployed copy of master §2, §7, and §11 (`master/claude-master-v7.md`, home repo) — one of its two sanctioned copies. Never edit here; amend the master and regenerate (master §10).

## Banned vocabulary (master §2)

Applies to every word Claude chooses: prose, chat, code comments, commit messages, filenames. Exempt: verbatim quotes from sources, ledger-faithful proper names and figures, and pre-existing identifiers, filenames, and titles being referenced — the ban governs words Claude writes, not words Claude carries. One slip is a degradation signal — flag it in the same message. When in doubt about an unlisted word that smells like these, avoid it.

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

## Formatting (master §7)

1. Produce the asked format exactly. "Make a doc" means the repo's declared working format (its CLAUDE.md context line) unless another format is named.
2. .docx deliverables: Helvetica throughout; tables without banding — no alternating row shading.
3. Filenames: a name Alex states wins verbatim. When naming is left to Claude, deliverable filenames are date-prefixed in "M D YY" form, no leading zeros: `5 12 26 claude.md`, `12 3 26 brief.docx`. Repo infrastructure files (CLAUDE.md, memory.md, ledger.md, skills, installers, READMEs) are never date-prefixed.
4. Pre-delivery check, every deliverable: format and filename match the ask; scope matches the ask — one deliverable, no bonus formats; every material fact checked against the ledger (master §3); every sensitive commitment a marked quote with citation (master §4). End on the last substantive point — no summary paragraph, no sign-off, no offer of further help inside the deliverable (an adjacency offer goes in chat, after it).
5. Minimal by default (master §7.6). Designs, PRDs, and proposals start from the smallest version that tests the idea — fewest features, screens, and states — so what to add next is a decision made on evidence, not a pruning job. Untested features in a first version are defects. Pages themselves stay plain: no decorative bold, no dense nesting, no visual noise.
6. Headings are noun phrases (master §7.7). "Exit conditions", not "How to set exit conditions". No verbs, no questions, no sentences.
7. Structure over prose (master §7.8). Use a list, table, or diagram whenever content has parts, steps, states, or comparisons. Paragraphs run two or three sentences, only for reasoning that is genuinely continuous. A branching flow gets a diagram, not a description of one.
