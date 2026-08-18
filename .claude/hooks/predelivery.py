#!/usr/bin/env python3
"""Pre-delivery check for prose deliverables.

Enforces the mechanically checkable part of the master's rules at write time,
so a violation is stopped before it ships instead of being caught in review.
The banned words and phrases are read from the deployed writing-standards
skill rather than copied here, so there is one source of truth (master §5.4).

Two ways to run:

    predelivery.py FILE [FILE ...]    check files already on disk
    predelivery.py --hook             PreToolUse hook, reads JSON on stdin

Standalone exit codes: 0 = clean or warnings only, 1 = blocking findings.
As a hook it always exits 0 and speaks through the JSON it prints, and it
fails open — any internal error lets the write through rather than wedging
the session.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BLOCK = "block"
WARN = "warn"

# .docx is absent on purpose: those are written through code, never through
# Write, so listing it would imply coverage that does not exist.
PROSE_SUFFIXES = {".md", ".markdown", ".mdx", ".txt", ".rst", ".adoc"}

# Files that enumerate the banned vocabulary. Scanning them would flag every
# rule for containing the word it bans.
RULE_FILES = {
    ".claude/universal.md",
    ".claude/skills/writing-standards/SKILL.md",
}
# "scratchpad" is deliberately absent: a draft written there and moved with a
# shell command is an ordinary working pattern, and exempting it produces an
# unchecked deliverable.
RULE_DIRS = {".git", "node_modules", ".venv"}
# These hold the rule text, but only in the home repo. Anywhere else they are
# ordinary directory names and must not exempt a whole tree from every check.
HOME_ONLY_DIRS = {"master", "install"}

# Never date-prefixed (master §7.4).
INFRA_NAMES = {
    "CLAUDE.md",
    "CLAUDE.local.md",
    "README.md",
    "index.md",
    "ledger.md",
    "SKILL.md",
    "universal.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "LICENSE.md",
}

# Acronyms common enough that spelling them out would read as padding.
# Anything outside this list needs a gloss on first use (master §1.6).
ACRONYM_OK = {
    "AI", "API", "ARR", "CEO", "CFO", "COO", "CTO", "CI", "CD", "CLI", "CSS",
    "CSV", "DNS", "EU", "FAQ", "GB", "GDP", "GPU", "HTML", "HTTP", "HTTPS",
    "ID", "IP", "IT", "JSON", "KB", "MB", "MCP", "OK", "OS", "PDF", "PR",
    "RAM", "REST", "SDK", "SQL", "SSH", "TB", "TV", "UI", "UK", "URL", "US",
    "USA", "USD", "UTC", "UX", "VC", "XML", "YAML", "PM", "AM", "Q1", "Q2",
    "Q3", "Q4", "FY", "TODO", "NDA", "IPO", "CEO", "LLC", "VAT", "KPI",
}

# What "the rules loaded" means, in one place: the selftest and the per-write
# guard must not be able to disagree.
VOCAB_FLOOR = {"outright": 20, "replace": 8, "sense": 25, "openers": 3, "phrases": 40}

_ABBREV = (
    r"(?<!\bMr)(?<!\bMrs)(?<!\bMs)(?<!\bDr)(?<!\bSt)(?<!\bJr)(?<!\bSr)"
    r"(?<!\bvs)(?<!\betc)(?<!\bNo)(?<!\bapprox)(?<!\bFig)(?<!\bal)"
    r"(?<!\be\.g)(?<!\bi\.e)(?<!\bU\.S)(?<!\bInc)(?<!\bLtd)(?<!\bCo)"
)
# The next sentence may open lower-case. Requiring a capital collapsed a whole
# paragraph to one sentence whenever it did — `one here. two follow. three is
# plenty. four is too many.` counted as one and the cap never fired (audit
# round three). A digit or a bullet marker opens one too. What must NOT open one
# is a lower-case continuation of an abbreviation, which _ABBREV already
# handles.
SENTENCE_END = re.compile(
    _ABBREV + r"[.!?]+[\"')\]]*(?:\s+|$)(?=[A-Za-z0-9\"'(\[\-*]|$)")

DATE_PREFIX = re.compile(r"^(?:[1-9]|1[0-2]) (?:[1-9]|[12]\d|3[01]) \d{2} \S")
BAD_DATE_PREFIX = re.compile(r"^(\d{1,2})[_\-.](\d{1,2})[_\-.](\d{2,4})[_\-.]")

FIGURE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?\s*(?:bn?|m|k|billion|million|thousand|trillion)?\b"
    r"|\b\d+(?:\.\d+)?\s?%"
    r"|\b\d+(?:\.\d+)?x\b",
    re.IGNORECASE,
)
LEDGER_ENTRY = re.compile(r"^\s*[-*]\s*\[\d{4}-\d{2}-\d{2}\]", re.MULTILINE)

LITOTES = re.compile(
    r"\bnot\s+(?:bad|uncommon|unlike|unusual|without\s+merit|insignificant|"
    r"unimportant|impossible|unheard\s+of|unhelpful|unreasonable|unclear|"
    r"unlikely|untrue|unknown|dissimilar)\b|\bno\s+small\s+(?:feat|matter|thing)\b",
    re.IGNORECASE,
)
CLOSER_OPENERS = re.compile(
    r"^\s*(?:in conclusion|in summary|to sum up|to summarise|to summarize|"
    r"overall|ultimately)\b[,:]?",
    re.IGNORECASE,
)
SIGN_OFF = re.compile(
    r"i hope this helps|hope that helps|let me know if|feel free to (?:ask|reach)|"
    r"happy to help|don't hesitate to",
    re.IGNORECASE,
)
QUESTION_HEAD = re.compile(r"^(?:how|why|what|when|where|who|which|should|can|do|does|is|are)\b", re.I)
# "Seven avenues, ranked" — a verdict with the judge and the basis deleted.
VERDICT_HEAD = re.compile(r",\s+\w+(?:ed|en)\b\s*$", re.I)
# A bold-only line sitting directly above a heading is a kicker.
BOLD_ONLY = re.compile(r"^\s*\*\*[^*]{2,80}\*\*\s*$")
SENTENCE_HEAD = re.compile(r"\s(?:is|are|was|were|will|should|can|could|must|does|do)\s", re.I)
# "The thing to lead with tomorrow" carries a verb; "Research to decision" is
# a noun phrase, so match a verb after "to" rather than any word.
INFINITIVE_HEAD = re.compile(
    r"\bto (?:lead|do|use|make|build|set|run|get|know|watch|ask|say|avoid|fix|"
    r"start|ship|pick|choose|decide|read|write|send|take|keep|check|handle)\b",
    re.I,
)
# "Design for the machine path" is an instruction; "Design decisions" is a noun
# phrase, and both open with the same word. The second token separates them: an
# imperative is followed by a determiner, preposition or pronoun, while a noun
# phrase is followed by its noun. Narrow on purpose — it under-reports rather
# than firing on a legitimate heading, since a checker that cries wolf on good
# headings gets routed around.
IMPERATIVE_VERBS = (
    "design|read|learn|enter|unify|give|treat|build|close|frame|prompt|curate|exploit|"
    "evaluate|optimize|optimise|use|make|set|run|get|know|watch|ask|say|avoid|fix|start|"
    "ship|pick|choose|decide|write|send|take|keep|check|handle|add|remove|delete|create|"
    "define|record|report|review|test|verify|measure|track|plan|draft|send|store|load|"
    "install|configure|deploy|monitor|scale|reduce|increase|improve|protect|prevent|"
    "ensure|confirm|collect|gather|apply|adopt|follow|stop|begin|finish|prepare|manage"
)
IMPERATIVE_FOLLOWERS = (
    "a|an|the|your|our|their|its|his|her|my|every|each|all|any|some|this|that|these|those|"
    "for|before|after|when|while|with|by|to|from|into|in|on|at|through|toward|towards|"
    "against|about|across|around|over|under|it|them|us|me|him|why|how|what|where"
)
# -ing words that are ordinary nouns rather than gerunds taking an object.
NOUN_ING = {
    "monitoring", "training", "sampling", "positioning", "pricing", "messaging",
    "engineering", "funding", "marketing", "planning", "reporting", "testing",
    "tooling", "onboarding", "forecasting", "accounting", "underwriting",
    "servicing", "staking", "hedging", "clearing", "netting", "backtesting",
    "logging", "tracing", "caching", "routing", "sharding", "streaming",
    "batching", "learning", "reasoning", "grounding", "banking", "lending",
    "borrowing", "settlement", "wording", "framing", "packaging", "branding",
}
IMPERATIVE_HEAD = re.compile(
    rf"^(?:\d+[.)]\s*)?(?:{IMPERATIVE_VERBS})\s+(?:{IMPERATIVE_FOLLOWERS})\b",
    re.I,
)


class Finding:
    __slots__ = ("severity", "rule", "line", "message", "span")

    def __init__(self, severity: str, rule: str, line: int, message: str,
                 span: str = "") -> None:
        # What was actually wrong, not just what kind of thing was wrong. The
        # demotion below keys on it: without a span, a second four-sentence
        # paragraph produced a message byte-identical to the first one's and was
        # demoted to a warning, so adding a new break of a class the file already
        # carried went unblocked.
        self.span = span
        self.severity = severity
        self.rule = rule
        self.line = line
        self.message = message

    def render(self, path: str) -> str:
        where = f"{path}:{self.line}" if self.line else path
        return f"  [{self.rule}] {where} — {self.message}"


# --------------------------------------------------------------------------
# Reading the rules out of the deployed skill
# --------------------------------------------------------------------------

def find_repo_root(start: Path) -> Path | None:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists() or (candidate / ".claude").is_dir():
            return candidate
    return None


def read_text(path: Path) -> str | None:
    """Read a file for checking.

    Undecodable bytes become U+FFFD rather than raising. UnicodeDecodeError is
    a ValueError, so it escapes every OSError handler and lands in the mute
    top-level catch: one latin-1 byte in someone else's file would switch the
    checker off for every write, invisibly and until the file is re-encoded.
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def load_vocabulary(root: Path | None) -> dict:
    """Pull the banned lists out of the writing-standards skill.

    Returns empty lists when the skill is missing, so a repo without the
    bundle still gets the structural checks.
    """
    empty = {"outright": [], "replace": {}, "sense": {}, "openers": [], "phrases": []}
    # Prefer the skill shipped beside this hook. find_repo_root can bind to a
    # nested .git (a submodule, a vendored dependency) or to nothing at all for
    # a file outside any repo, and then every vocabulary check would pass on
    # everything without a word about it.
    skill = Path(__file__).resolve().parents[1] / "skills" / "writing-standards" / "SKILL.md"
    if not skill.is_file() and root is not None:
        skill = root / ".claude" / "skills" / "writing-standards" / "SKILL.md"
    if not skill.is_file():
        return empty
    text = read_text(skill)
    if text is None:
        return empty

    sections: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("### "):
            if current:
                sections[current] = "\n".join(buf)
            current = line[4:].strip().lower()
            buf = []
        elif line.startswith("## ") and current:
            sections[current] = "\n".join(buf)
            current = None
            buf = []
        elif current:
            buf.append(line)
    if current:
        sections[current] = "\n".join(buf)

    def find_section(*needles: str) -> str:
        for name, body in sections.items():
            if all(n in name for n in needles):
                return body
        return ""

    def comma_words(body: str) -> list[str]:
        # Every line of the block, not the first one. Returning on the first
        # meant a term added on a continuation line was loaded by nothing and
        # every check stayed green — the ban existed in the rules and was
        # enforced nowhere (audit round four). propagate.vocab_terms already
        # reads the whole block, so the two now agree.
        found: list[str] = []
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith(("-", "*", "#")):
                continue
            head = line.split(" — ")[0]
            found += [w.strip().lower() for w in head.split(",") if w.strip()]
        return found

    def bullet_terms(body: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for line in body.splitlines():
            line = line.strip()
            if not line.startswith("- "):
                continue
            body_text = line[2:]
            head, _, note = body_text.partition(" — ")
            if not note:
                continue
            for term in head.split(","):
                term = term.strip().lower()
                if term and " " not in term.strip("-"):
                    out[term] = note.strip()
                elif term:
                    out[term] = note.strip()
        return out

    outright = comma_words(find_section("banned outright"))
    replace = bullet_terms(find_section("replacement"))
    sense = bullet_terms(find_section("tell sense"))
    openers = comma_words(find_section("sentence-opening"))

    phrases: list[tuple[str, str]] = []
    for line in find_section("phrases and constructions").splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        body_text = line[2:]
        # Guidance follows the first em-dash that sits outside a quote. Text
        # after it holds replacements ("Say the thing: 'good', 'useful'"),
        # which must not be read back as banned phrases.
        quoted_blanked = re.sub(r'"[^"]*"', lambda m: " " * len(m.group(0)), body_text)
        split_at = quoted_blanked.find(" — ")
        head = body_text[:split_at] if split_at != -1 else body_text
        for quoted in re.findall(r'"([^"]{6,})"', head):
            # A quoted head can carry several banned phrases at once, either as
            # alternatives inside one pair of quotes ("serves as / stands as /
            # is a testament to") or with a trailing ellipsis standing for the
            # rest of the sentence ("Ever wondered..."). Stored verbatim, both
            # only matched text containing the literal slash or the literal
            # dots, so six entries could never fire against running prose.
            for part in quoted.split(" / "):
                part = part.strip()
                if len(part) >= 6:
                    phrases.append((part, body_text))

    return {
        "outright": outright,
        "replace": replace,
        "sense": sense,
        "openers": openers,
        "phrases": phrases,
    }


# --------------------------------------------------------------------------
# Masking: blank out regions where the rules do not apply, keeping offsets
# --------------------------------------------------------------------------

def fenced_spans(text: str) -> list[tuple[int, int]]:
    """Every fenced code block, as offsets into `text`.

    A fence opens at the start of a line and closes at the start of a line, and
    a run of N markers closes only on a run of N or more of the same character.
    Both halves are load-bearing and both were learned from a failure:

    - Matching ``` anywhere paired an inline ``` in prose with the next real
      fence and blanked everything between — real prose exempted from every
      check, and the code that should have been exempt left exposed instead
      (audit round two).
    - Ignoring the run length paired a four-marker opener with the three-marker
      opener nested inside it, so the nested block stayed exposed. Measured on
      real traffic 2026-08-18: two of the sixty-one plain-speech hits since the
      check shipped were this, both in a document quoted into chat because Alex
      asked for it.

    An unclosed fence runs to the end of the text rather than swallowing a
    later pair.
    """
    spans: list[tuple[int, int]] = []
    open_at: int | None = None
    marker = ""
    offset = 0
    for line in text.splitlines(keepends=True):
        run = re.match(r"(`{3,}|~{3,})", line)
        if run:
            token = run.group(1)
            if open_at is None:
                open_at, marker = offset, token
            elif token[0] == marker[0] and len(token) >= len(marker):
                spans.append((open_at, offset + len(line)))
                open_at, marker = None, ""
        offset += len(line)
    if open_at is not None:
        spans.append((open_at, len(text)))
    return spans


def mask(text: str) -> str:
    """Replace code, links and comments with spaces of equal length.

    Offsets and line numbers stay valid, so findings still point at the
    right line.
    """
    out = list(text)

    def blank(start: int, end: int) -> None:
        for i in range(start, min(end, len(out))):
            if out[i] != "\n":
                out[i] = " "

    # Front matter, anchored to the very top. Unanchored, this reads any pair
    # of `---` section rules as front matter and blanks everything between
    # them, which switches every check off for that stretch without saying so.
    front = re.match(r"\A---\n.*?\n---\n", text, re.DOTALL)
    if front:
        blank(front.start(), front.end())

    # Spans that legitimately cross lines. DOTALL belongs to these only.
    for start, end in fenced_spans(text):
        blank(start, end)
    for m in re.finditer(r"<!--.*?-->", text, re.DOTALL):
        blank(m.start(), m.end())

    # Line-bound spans. DOTALL must never reach these: it lets `.` match a
    # newline, so a greedy `.*$` runs from the first match to the end of the
    # file and one blockquote blanks every rule out of everything after it,
    # without a word. Measured before this split: one blockquote line blanked
    # 99.5% of a 98,000-character file and the checker reported it clean.
    #
    # Carried text, exempt under §2 because Claude did not choose it: §4.1
    # requires source terms verbatim, so the ban must not reach inside a
    # blockquote or a ledger entry.
    for pattern in (
        r"`[^`\n]+`",           # inline code
        r"\]\([^)\n]*\)",       # link targets
        r"https?://\S+",
        r"^[ \t]*>.*$",                                # blockquoted source
        r"^[ \t]*[-*][ \t]*\[\d{4}-\d{2}-\d{2}\].*$",  # ledger entries (§3.4)
    ):
        for m in re.finditer(pattern, text, re.MULTILINE):
            blank(m.start(), m.end())

    # Quoted spans, paired in document order. A regex cannot do this: with a
    # minimum span length a short quoted term ("MVP") fails to pair, and the
    # scanner then joins its closing quote to the next term's opening quote,
    # blanking every rule out of the prose between them. Pairing in order
    # cannot skip a quote. A blank line inside means the quote never closed.
    # Scan what has already been masked, not the original. Code fences, inline
    # spans and links are blanked by this point, so a stray quote inside one —
    # an `awk -F"` line, a shell string — can no longer pair with a real opening
    # quote in the prose and blank everything between them. That bug turned a
    # legitimate §4 citation into an unquoted commitment. Two sessions found and
    # fixed this independently on 2026-08-13, with the same fix.
    # Walk openers and closers rather than zipping positions. Pairing the 1st
    # with the 2nd, the 3rd with the 4th and so on means ONE unpaired quote
    # shifts every pair after it, and the mask inverts: prose gets blanked and
    # quoted material gets scanned. Measured — `The gap is 5" wide. This
    # holistic approach delves into utilize territory per "the memo".` produced
    # zero findings, the same line without the inch-mark produced three, and the
    # reverse case scanned words inside a §4 citation that §2 exempts.
    #
    # A quote preceded by a word character and followed by one cannot be either
    # end of a quotation — that is an inch-mark, an apostrophe-s, a code
    # artefact — so it is skipped rather than allowed to shift the pairing.
    partial = "".join(out)
    open_straight = None
    for m in re.finditer(r"\"", partial):
        before = partial[m.start() - 1] if m.start() else " "
        after = partial[m.end()] if m.end() < len(partial) else " "
        if open_straight is None:
            if after.isspace() or after in ")]}.,;:!?":
                continue          # cannot open a quotation
            open_straight = m.start()
        else:
            if before.isspace() or before == "\n":
                continue          # cannot close one
            if "\n\n" not in partial[open_straight:m.end()]:
                # m.end() already sits past the closing quote. The extra +1 ate
                # the sentence terminator after it, so `He said "yes". Then he
                # left.` counted as one sentence (audit round two).
                blank(open_straight, m.end())
            open_straight = None
    open_at = None
    for m in re.finditer(r"[“”]", partial):
        if m.group(0) == "“" and open_at is None:
            open_at = m.start()
        elif m.group(0) == "”" and open_at is not None:
            if "\n\n" not in partial[open_at:m.end()]:
                blank(open_at, m.end())
            open_at = None
    return "".join(out)


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


LIST_MARKER = re.compile(r"^([-*+]|\d+[.)])\s+")


def prose_blocks(masked: str) -> list[tuple[int, str, bool]]:
    """Blocks of running prose, as (line, text, is_list_item).

    A list item is its own block: a seven-sentence run behind one bullet is
    the same paragraph, and without this the sentence cap is cleared by adding
    a dash — which is what the cap's own message tells the writer to do.
    """
    blocks: list[tuple[int, str, bool]] = []
    current: list[str] = []
    start_line = 0

    def flush() -> None:
        nonlocal current
        if current:
            blocks.append((start_line, " ".join(current), False))
            current = []

    for number, raw in enumerate(masked.splitlines(), start=1):
        stripped = raw.strip()
        if LIST_MARKER.match(stripped):
            flush()
            blocks.append((number, LIST_MARKER.sub("", stripped), True))
        elif not stripped or stripped.startswith(("#", "|", ">")):
            flush()
        else:
            if not current:
                start_line = number
            current.append(stripped)
    flush()
    return blocks


# A token ending in a period that is an abbreviation rather than a sentence end:
# an initial (`J.`), a dotted form (`p.m.`, `U.K.`, `e.g.`), or a short word
# followed by a lower-case continuation. Checked on the token rather than kept
# in a list, because the list can never be complete — allowing a lower-case or
# digit start (needed, or a whole lower-case paragraph counted as one sentence)
# made every unlisted abbreviation read as a sentence end, and the gate then
# blocked messages that were inside the cap (audit round four).
# Initials (`J.`) and dotted forms (`p.m.`, `U.K.`, `e.g.`) only. A general
# "short word" rule swallowed real sentence ends — `one here. two follow.`
# counted as two because `here.` is five letters.
ABBREV_SHAPE = re.compile(r"(?:^|\s)(?:[A-Za-z]\.|(?:[A-Za-z]\.){2,})$")


def count_sentences(paragraph: str) -> int:
    text = paragraph.strip()
    if not text:
        return 0
    real = 0
    for m in SENTENCE_END.finditer(text):
        before = text[:m.start() + 1]
        after = text[m.end():m.end() + 1]
        # A capital after the break settles it: an abbreviation can precede a
        # real sentence end too ("...at 3 p.m. We left.").
        if after and (after.isupper() or after in "\"'([") or not after:
            real += 1
            continue
        if ABBREV_SHAPE.search(before):
            continue        # `p.m. today`, `vs. 4`, `Fig. 2` — one sentence
        real += 1
    return max(1, real)


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def check_filename(path: Path, root: Path | None) -> list[Finding]:
    if path.suffix.lower() not in PROSE_SUFFIXES:
        return []
    if path.name in INFRA_NAMES:
        return []
    rel = relative(path, root)
    if any(part in RULE_DIRS for part in Path(rel).parts):
        return []
    # Memory-graph nodes are infrastructure, not deliverables: their filename is
    # the node id (master §6.4), so a date prefix would break the id/file match.
    if Path(rel).parts and Path(rel).parts[0] in {".claude", "skills-library", ".github", "docs", "memory"}:
        return []
    stem = path.name
    if DATE_PREFIX.match(stem):
        return []
    bad = BAD_DATE_PREFIX.match(stem)
    if bad:
        month, day, year = bad.group(1), bad.group(2), bad.group(3)[-2:]
        rest = stem[bad.end():].replace("_", " ").replace("-", " ")
        suggestion = f"{int(month)} {int(day)} {year} {rest}"
        return [Finding(BLOCK, "filename", 0,
                        f"master §7.4 wants spaces and no leading zeros in the date prefix. "
                        f"Rename to: {suggestion!r}")]
    # §7.4 opens "a name Alex states wins verbatim" and applies the date form
    # only when naming is left to Claude. The hook cannot see the ask, so which
    # clause governs is a judgement — warn, never block (master §9.5).
    return [Finding(WARN, "filename", 0,
                    "master §7.4: when naming is left to Claude, deliverable filenames start "
                    "with a date in 'M D YY' form, no leading zeros, e.g. '8 11 26 review.md'. "
                    "A name Alex stated wins verbatim — ignore this if he named the file.")]


def allowed_terms(text: str) -> set[str]:
    """Terms the file declares as carried, not chosen (master §2 exemption).

    A file quoting a proper name or an established term of art marks it with
    `<!-- predelivery-allow: hidden gem, moat -->` and the ban steps aside.
    """
    out: set[str] = set()
    for m in re.finditer(r"<!--\s*predelivery-allow:\s*([^>]+?)\s*-->", text, re.I):
        out.update(t.strip().lower() for t in m.group(1).split(",") if t.strip())
    return out


def check_vocabulary(text: str, masked: str, vocab: dict) -> list[Finding]:
    found: list[Finding] = []
    lowered = masked.lower()
    exempt = allowed_terms(text)
    if exempt:
        # The pardon is read out of the file being written, so the same write
        # can carry its own. Recording it keeps that visible rather than silent.
        found.append(Finding(WARN, "exemption", 0,
                             f"§2 exemption claimed for: {', '.join(sorted(exempt))}. Valid only "
                             f"for a term carried from a source, never for a word Claude chose."))

    for word in vocab["outright"]:
        if word in exempt:
            continue
        for m in re.finditer(rf"\b{re.escape(word)}\w*\b", lowered):
            found.append(Finding(BLOCK, "banned-word", line_of(masked, m.start()),
                                 f"master §2 bans {word!r} outright."))
            break

    for word, note in vocab["replace"].items():
        if word in exempt:
            continue
        for m in re.finditer(rf"\b{re.escape(word)}\w*\b", lowered):
            found.append(Finding(BLOCK, "banned-word", line_of(masked, m.start()),
                                 f"master §2: {word!r} — {note}"))
            break

    for word, note in vocab["sense"].items():
        if word in exempt:
            continue
        for m in re.finditer(rf"\b{re.escape(word)}\w*\b", lowered):
            found.append(Finding(WARN, "banned-sense", line_of(masked, m.start()),
                                 f"master §2: {word!r} — {note}"))
            break

    for word in vocab["openers"]:
        for m in re.finditer(rf"(?:^|(?<=[.!?])\s+){re.escape(word)}\b", lowered, re.MULTILINE):
            found.append(Finding(BLOCK, "banned-opener", line_of(masked, m.start()),
                                 f"master §2 bans {word!r} as a sentence-opening transition."))
            break

    for phrase, source in vocab["phrases"]:
        if phrase.lower() in exempt:
            continue
        # Split on the placeholders FIRST, then escape each literal run. The old
        # order escaped the whole phrase and substituted afterwards, so a phrase
        # opening on a placeholder ("X — not Y — Z") kept that first placeholder
        # literal and matched nothing. `Z` was missing from the class outright,
        # and an ellipsis ("Ever wondered why...?") stands for the same thing:
        # arbitrary text the writer supplies.
        parts = re.split(r"\b[XYZ]\b|\s*\.\.\.\s*", phrase)
        placeholder = len(parts) > 1
        pattern = r"[\w' -]{2,30}".join(re.escape(p.lower()) for p in parts if p)
        try:
            m = re.search(pattern, lowered)
        except re.error:
            continue
        if m:
            severity = WARN if placeholder else BLOCK
            found.append(Finding(severity, "banned-phrase", line_of(masked, m.start()),
                                 f"master §2: {source}"))
    return found


def check_structure(masked: str, prose_cap: int = 3) -> list[Finding]:
    found: list[Finding] = []

    for number, raw in enumerate(masked.splitlines(), start=1):
        m = re.match(r"^(#{1,6})\s+(.*)$", raw)
        if not m:
            continue
        head = m.group(2).strip().rstrip("#").strip()
        if not head:
            continue
        if head.endswith("?"):
            found.append(Finding(BLOCK, "heading", number,
                                 f"master §7.7: headings are noun phrases, not questions — {head!r}"))
            continue
        if VERDICT_HEAD.search(head):
            found.append(Finding(BLOCK, "heading", number,
                                 f"master §7.7: a comma plus a past participle reads as a verdict "
                                 f"and deletes who judged and on what basis — {head!r}. State the "
                                 f"claim in full or drop it."))
            continue
        if QUESTION_HEAD.match(head):
            found.append(Finding(WARN, "heading", number,
                                 f"master §7.7: heading opens as a question or instruction, "
                                 f"use the noun form — {head!r}"))
            continue
        if head.endswith("."):
            found.append(Finding(WARN, "heading", number,
                                 f"master §7.7: heading reads as a sentence — {head!r}"))
            continue
        words = head.split()
        first = words[0]
        # "Messaging hierarchy" and "Pricing research" are noun phrases that
        # happen to start in -ing. "Setting exit conditions" is the banned
        # form, and it runs longer.
        gerund = len(words) > 2 and first.lower().endswith("ing") and len(first) > 5
        # Some -ing words are ordinary nouns in these subjects, and a heading
        # built on one is a noun phrase already: "Monitoring and observability",
        # "Training data — what a model learns from". Coordination is the other
        # tell: a gerund taking an object never reads "X and Y".
        second = words[1].lower().strip(",:;") if len(words) > 1 else ""
        # A determiner or possessive after the -ing word means it is taking an
        # object, which is the banned form however ordinary the word is as a
        # noun: "Planning an AI application" fires, "Planning horizon" does not.
        takes_object = second in ("a", "an", "the", "your", "our", "its", "their",
                                  "his", "her", "my", "what", "how", "which",
                                  "this", "that", "these", "those")
        if gerund and not takes_object and (first.lower().strip(",:—-") in NOUN_ING
                                            or second in ("and", "or")):
            gerund = False
        if gerund:
            found.append(Finding(WARN, "heading", number,
                                 f"master §7.7: gerund heading, use the noun form — {head!r}"))
        elif IMPERATIVE_HEAD.match(head):
            found.append(Finding(WARN, "heading", number,
                                 f"master §7.7: heading is an instruction, not a noun phrase — "
                                 f"{head!r}. Name the thing, not the action."))
        elif SENTENCE_HEAD.search(head) or INFINITIVE_HEAD.search(head):
            found.append(Finding(WARN, "heading", number,
                                 f"master §7.7: heading carries a verb — {head!r}"))

    # A bold-only line sitting directly above a heading is a kicker: two
    # headings carrying one idea (master §7.7).
    lines = masked.splitlines()
    for number, raw in enumerate(lines, start=1):
        if not BOLD_ONLY.match(raw):
            continue
        for nxt in lines[number:]:
            if not nxt.strip():
                continue
            if re.match(r"^#{1,6}\s+\S", nxt):
                found.append(Finding(BLOCK, "heading", number,
                                     f"master §7.7: kicker stacked above a heading — "
                                     f"{raw.strip()!r}. Keep it only if it carries what the "
                                     f"heading does not, such as a number or a section name."))
            break

    blocks = prose_blocks(masked)

    for start_line, paragraph, is_item in blocks:
        count = count_sentences(paragraph)
        if count > prose_cap:
            where = "list item" if is_item else "paragraph"
            fix = "Split the item." if is_item else "Use a list or table."
            written = "two" if prose_cap == 2 else "three"
            rule = "§1.3a" if prose_cap == 2 else "§7.8"
            found.append(Finding(BLOCK, "paragraph", start_line,
                                 f"master {rule}: prose caps at {written} sentences, this "
                                 f"{where} has {count}. {fix}",
                                 span=" ".join(paragraph.split())[:60]))

    # Only asides inside running prose count. An em-dash separating a term
    # from its definition in a list or table is the house style, not the
    # contrast tic §2 bans.
    prose = " ".join(body for _, body, is_item in blocks if not is_item)
    words = len(prose.split())
    dashes = prose.count("—")
    allowed = max(1, round(words / 500))
    if dashes > allowed:
        found.append(Finding(WARN, "em-dash", 0,
                             f"master §2: at most one em-dash aside per ~500 words of prose. "
                             f"Found {dashes} across {words} words (allowed {allowed})."))

    for m in LITOTES.finditer(masked):
        found.append(Finding(BLOCK, "litotes", line_of(masked, m.start()),
                             f"master §2 bans litotes — say the thing, not its opposite denied: "
                             f"{m.group(0)!r}"))
        break

    if blocks:
        last_line, last, _ = blocks[-1]
        if CLOSER_OPENERS.match(last):
            found.append(Finding(BLOCK, "closer", last_line,
                                 "master §2 and §7.5: end on the last substantive point, "
                                 "no summary paragraph."))
        m = SIGN_OFF.search(last)
        if m:
            found.append(Finding(BLOCK, "closer", last_line,
                                 f"master §7.5: no sign-off or offer of further help inside a "
                                 f"deliverable — {m.group(0)!r}"))
    return found


def check_acronyms(masked: str) -> list[Finding]:
    found: list[Finding] = []
    seen: set[str] = set()
    for m in re.finditer(r"\b([A-Z]{2,6})s?\b", masked):
        token = m.group(1)
        if token in ACRONYM_OK or token in seen:
            continue
        # Part of a filename (CLAUDE.md, SKILL.md), not an acronym in prose.
        if re.match(r"\.[A-Za-z]{1,5}\b", masked[m.end():m.end() + 6]):
            continue
        seen.add(token)
        glossed = (
            re.search(rf"\({re.escape(token)}s?\)", masked)
            or re.search(rf"\b{re.escape(token)}s?\s*\([a-z]", masked)
            or re.search(rf"\b{re.escape(token)}s?\s*[—-]\s*[a-z]", masked)
        )
        if glossed:
            continue
        found.append(Finding(WARN, "acronym", line_of(masked, m.start()),
                             f"master §1.6: gloss {token!r} in a few words on first use, "
                             f"or spell it out."))
    return found


def is_reference(path: Path, root: Path | None) -> bool:
    """Teaching material, where figures are worked examples rather than facts.

    `docs/` is not on this list: in an ordinary repo it is where a deliverable
    lands, and .md is the working format, so exempting it silently drops the
    check on the most likely path of all.
    """
    parts = Path(relative(path, root).replace("\\", "/")).parts
    if not parts:
        return False
    if parts[0] == ".claude":
        return True
    return parts[0] == "skills-library" and is_home_repo(root)


def check_ledger(path: Path, masked: str, root: Path | None) -> list[Finding]:
    if root is None or is_reference(path, root):
        return []
    figures = {m.group(0) for m in FIGURE.finditer(masked)}
    if len(figures) < 3:
        return []
    # A --private install lands as CLAUDE.local.md beside the target's own
    # tracked CLAUDE.md, and §3.2 puts the ledger in the bundle's file. Reading
    # only CLAUDE.md turns this check off in exactly the repos Alex does not
    # own, where the figures are someone else's money.
    local = root / "CLAUDE.local.md"
    declaring = local if local.is_file() else root / "CLAUDE.md"
    if not declaring.is_file():
        return []
    declared = read_text(declaring)
    if declared is None:
        return []
    if "Ledger" not in declared:
        return [Finding(WARN, "ledger", 0,
                        f"master §3.2: {declaring.name} declares no ledger line, so the §3.3 "
                        f"check cannot run on {len(figures)} material figures here.")]
    pool = declared
    ledger_file = root / "ledger.md"
    if ledger_file.is_file():
        extra = read_text(ledger_file)
        if extra is not None:
            pool += extra
    entries = "\n".join(line for line in pool.splitlines() if LEDGER_ENTRY.match(line))
    recorded = {m.group(0).lower().replace(" ", "") for m in FIGURE.finditer(entries)}
    missing = sorted(f for f in figures if f.lower().replace(" ", "") not in recorded)
    if not missing:
        return []
    sample = ", ".join(missing[:4])
    # Whether a figure is material is §3.1's cost test, which a regex cannot
    # run — so warn, never block (master §9.5), the same call check_filename
    # makes. Matching figure by figure also closes the bypass where one
    # unrelated dated bullet satisfied the gate for that repo forever.
    return [Finding(WARN, "ledger", 0,
                    f"master §3.3: {len(missing)} figure(s) here are not in the ledger "
                    f"({sample}{' …' if len(missing) > 4 else ''}). If any is material — would "
                    f"it cost something to be wrong? — record it as "
                    f"'- [YYYY-MM-DD] subject — fact (source)' before first use.")]


# --------------------------------------------------------------------------
# Driving
# --------------------------------------------------------------------------

def relative(path: Path, root: Path | None) -> str:
    if root is None:
        return path.name
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return path.name


def is_home_repo(root: Path | None) -> bool:
    # Matched by shape, not by version: a v8 master must not silently turn the
    # home repo into an ordinary one.
    # The rules moved into the graph on 2026-08-14; the home repo is the one
    # that holds them.
    return root is not None and (root / "memory" / "rules.md").is_file()


def is_rule_file(path: Path, root: Path | None) -> bool:
    rel = relative(path, root).replace("\\", "/")
    if rel in RULE_FILES:
        return True
    parts = Path(rel).parts
    if any(part in RULE_DIRS for part in parts):
        return True
    return bool(parts) and parts[0] in HOME_ONLY_DIRS and is_home_repo(root)


def is_memory_file(path: Path, root: Path | None) -> bool:
    """A memory-graph domain file, which §6.3 exempts from §7.7 headings."""
    parts = Path(relative(path, root).replace("\\", "/")).parts
    return bool(parts) and parts[0] == "memory" and is_home_repo(root)


def is_capture_file(path: Path, root: Path | None) -> bool:
    """`memory/inbox/` — Alex's own words, written by the capture hook.

    Nothing here is authored for a reader and nothing here may be edited by
    hand: the quote is what §4 protects. Checking it against the writing rules
    reported seven paragraph breaks that a session is forbidden to fix, so the
    sweep listed permanent work and the real backlog was seven items smaller
    than it looked. §2 already exempts words Claude did not choose.
    """
    parts = Path(relative(path, root).replace("\\", "/")).parts
    return len(parts) >= 2 and parts[0] == "memory" and parts[1] == "inbox"


WORD_BUDGET = {
    ".claude/universal.md": 3150,
    "CLAUDE.md": 200,
}


def check_budget(path: Path, content: str, root: Path | None) -> list[Finding]:
    """Master §5.1a: the always-loaded rules are zero-sum.

    Runs before the rule-file exemption below, deliberately. `check()` returns
    early for rule files, so the one file whose growth is the problem is the one
    file nothing was watching. This is measured in words, not lines: a line cap
    is defeated by writing longer lines, which is exactly what happened.
    """
    rel = relative(path, root).replace("\\", "/")
    budget = WORD_BUDGET.get(rel)
    if budget is None:
        return []
    # The 200-word cap is on the CLAUDE.md this system installs, and that file
    # lives in the fifteen target repos, not here — where it was the only place
    # the check ran. The bundle's copy is the one carrying the universal.md
    # import; a repo's own CLAUDE.md is flagged, never trimmed (§5.1), so it is
    # left to the home-repo path.
    ours = "@.claude/universal.md" in content
    if not is_home_repo(root) and not ours:
        return []
    words = len(content.split())
    if words <= budget:
        return []
    if rel != ".claude/universal.md" and not is_home_repo(root):
        # A kitted repo's CLAUDE.md holds no rules to retire: §5.1 lets it carry
        # only the import, the context line, the ledger line, settled decisions
        # and the amendment note, and the rules it imports are amended in the
        # home repo, which this session may not even be able to read. What grows
        # there is the ledger, so name the move §3.2 asks for. "Retire a rule to
        # land one" was advice no downstream session could act on, and it landed
        # as a BLOCK on every further write to the file — measured at the tenth
        # ledger entry, eleven before the old rule said to migrate.
        return [Finding(BLOCK, "budget", 0,
                        f"master §5.1a: {rel} is {words} words against a budget of {budget}. "
                        f"Move the ledger into `ledger.md` at the repo root and point the "
                        f"ledger line at it (§3.2); {rel} carries only the import, the context "
                        f"line, the ledger line, settled decisions and the amendment note "
                        f"(§5.1). Do not trim silently.")]
    return [Finding(BLOCK, "budget", 0,
                    f"master §5.1a: {rel} is {words} words against a budget of {budget}. "
                    f"The always-loaded rules are zero-sum — retire a rule to land one, or "
                    f"raise the budget with Alex (§10). Do not trim silently.")]


def check(path: Path, content: str, root: Path | None) -> list[Finding]:
    if path.suffix.lower() not in PROSE_SUFFIXES:
        return []
    budget = check_budget(path, content, root)
    if is_rule_file(path, root) or is_capture_file(path, root):
        return budget
    masked = mask(content)
    vocab = load_vocabulary(root)
    findings = budget + check_filename(path, root)
    # A partial load checks part of the list and reports clean on the rest, so
    # the floor is per-section, not "both lists empty".
    thin = [name for name, least in VOCAB_FLOOR.items() if len(vocab[name]) < least]
    if thin:
        findings.append(Finding(BLOCK, "hook", 0,
                                f"the writing-standards skill loaded short ({', '.join(thin)}), "
                                f"so §2 is not being checked for this write. "
                                f"Run predelivery.py --selftest."))
    findings += check_vocabulary(content, masked, vocab)
    structure = check_structure(masked)
    # A memory node's heading is a sentence on purpose (master §6.3): a noun
    # phrase would name the topic where the reader needs the finding. Warning on
    # every node write would teach the session to ignore this hook, so §7.7 is
    # dropped for the graph and every other structure rule still applies.
    if is_memory_file(path, root):
        structure = [f for f in structure if f.rule != "heading"]
    findings += structure
    # Glossing applies to deliverables Alex reads, not to reference material
    # where the domain terms are the subject. The ledger gate keys off the
    # figures in the text, so it runs everywhere.
    if DATE_PREFIX.match(path.name) or BAD_DATE_PREFIX.match(path.name):
        findings += check_acronyms(masked)
    findings += check_ledger(path, masked, root)
    return findings


def payload_to_target(payload: dict) -> tuple[Path, str] | None:
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    raw_path = tool_input.get("file_path")
    if not raw_path:
        return None
    path = Path(raw_path)
    if tool == "Write":
        return path, tool_input.get("content", "")
    if tool == "Edit":
        original = read_text(path)
        if original is None:
            return None
        old = tool_input.get("old_string", "")
        new = tool_input.get("new_string", "")
        if not old:
            return None
        if tool_input.get("replace_all"):
            return path, original.replace(old, new)
        return path, original.replace(old, new, 1)
    if tool == "MultiEdit":
        content = read_text(path)
        if content is None:
            return None
        for edit in tool_input.get("edits") or []:
            old = edit.get("old_string", "")
            new = edit.get("new_string", "")
            if not old:
                continue
            content = (content.replace(old, new) if edit.get("replace_all")
                       else content.replace(old, new, 1))
        return path, content
    return None


def run_hook() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    target = payload_to_target(payload)
    if target is None:
        return 0
    path, content = target
    root = find_repo_root(path.parent if path.parent.exists() else Path.cwd())
    findings = check(path, content, root)

    # Only what this write introduces may deny. A file's existing breaks belong
    # to whoever wrote them — §2 exempts words Claude did not choose, and
    # denying an unrelated one-line edit because a target's own maintainers
    # wrote "innovative" three paragraphs away teaches a session to route
    # around the hook entirely. Pre-existing breaks still surface as warnings.
    before = read_text(path)
    if before is not None and before != content:
        prior = {(f.rule, f.message, f.span) for f in check(path, before, root)}
        for finding in findings:
            # "the skill loaded short" is a fact about this write, not a break
            # the file's author owns. It is content-independent, so it sits in
            # `prior` on every edit and would demote itself out of existence —
            # cancelling the one guard that stops work when §2 is unenforced.
            if finding.rule == "hook":
                continue
            if finding.severity == BLOCK and (finding.rule, finding.message, finding.span) in prior:
                finding.severity = WARN

    if not findings:
        return 0

    rel = relative(path, root)
    blocking = [f for f in findings if f.severity == BLOCK]
    warnings = [f for f in findings if f.severity == WARN]

    if blocking:
        lines = [f"Pre-delivery check failed for {rel} — fix these, then write again:", ""]
        lines += [f.render(rel) for f in blocking]
        if warnings:
            lines += ["", "Also worth a look:"]
            lines += [f.render(rel) for f in warnings]
        reason = "\n".join(lines)
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            },
            "systemMessage": f"Pre-delivery check blocked {rel} ({len(blocking)} rule breaks).",
        }))
        return 0

    note = "\n".join([f"Pre-delivery warnings for {rel}:"] + [f.render(rel) for f in warnings])
    print(json.dumps({
        "systemMessage": note,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": note,
        },
    }))
    return 0


def _turn_text(transcript_path: str) -> tuple[list[str], str | None]:
    """Assistant text blocks written since the last real user turn.

    The transcript is an undocumented internal format with no stability
    guarantee, so every step here fails loudly rather than returning an empty
    list, which would read as "nothing to check" and pass silently.
    """
    path = Path(transcript_path)
    try:
        # Whole file, not a tail window. A long turn is exactly the turn most
        # worth checking, and a 256 KB tail dropped the start of it: measured on
        # this project's own transcript, 13 of 48 turns ran past the window, 153
        # assistant blocks fell outside it and 16 of those carried findings the
        # gate would have blocked. Worse, when the turn's own user entry fell
        # outside, the backward walk below found nothing, `start` stayed 0, and
        # the window was checked as though it were the turn.
        #
        # Cost measured on the same file: 428 ms to read and parse 14.6 MB
        # against a 20 s hook timeout. compaction.py dropped tail windows for
        # the same reason (CI-037).
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [], f"transcript unreadable: {exc}"

    entries = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    if not entries:
        return [], "no parseable entries in the transcript tail"

    def is_real_user(entry: dict) -> bool:
        if entry.get("type") != "user" or entry.get("isSidechain") or entry.get("isMeta"):
            return False
        content = (entry.get("message") or {}).get("content")
        if isinstance(content, list):
            # A tool result is delivered as a user entry; it is not Alex speaking.
            return not any(b.get("type") == "tool_result" for b in content)
        return True

    start = 0
    for index in range(len(entries) - 1, -1, -1):
        if is_real_user(entries[index]):
            start = index + 1
            break

    blocks = []
    for entry in entries[start:]:
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "text" and block.get("text", "").strip():
                blocks.append(block["text"])
    return blocks, None


CHAT_PROSE_CAP = 2   # §1.3a, anything addressed to Alex directly
FILE_PROSE_CAP = 3   # §7.8, a document written for someone else


# Words that mean nothing outside this machine. §1.6 bans them in anything
# addressed to Alex; nothing enforced it until 2026-08-18, when he said the
# conversation "looks alien" for the third time.
#
# Scoped to what he has actually objected to, and no wider. File paths are
# deliberately absent: `mask()` blanks backticked spans, none of the 24 real
# messages measured carried a bare path, and a raw-text path pattern collides
# with the rule's own carve-out for a file he asked for by name.
JARGON = [
    (re.compile(r"§\s?\d"), "a § number"),
    (re.compile(r"\b(?:CI|RU|RW|VD|NS|FH|WC|PK)-\d{3,}\b"), "a memory-node id"),
    (re.compile(r"\bfb-\d{4}-\d{2}-\d{2}-[0-9a-f]{6,}\b"), "a capture-record id"),
    (re.compile(r"(?i)\b(?:commit|committed|rebase[d]?|force-push(?:ed)?|merge[d]?\s+the\s+pr|"
                r"pull request|PR\s*#\d+|branch(?:es)?|trunk|origin/\w+|HEAD|stash(?:ed)?|"
                r"cherry-pick(?:ed)?|squash(?:ed)?)\b"), "git jargon"),
    (re.compile(r"(?i)\b(?:stdout|stderr|stdin|regex|repo(?:sitory)?|selftest|"
                r"CI\s+(?:green|red|passed|failed)|exit\s+code|traceback|"
                r"hook(?:s)?\b(?!\s+(?:up|into\s+you)))\b"), "a machine word"),
]
# Said to Alex often enough, and harmless enough, that flagging them is noise.
JARGON_OK = re.compile(r"(?i)\b(?:branches?\s+of\s+a\s+tree|merged?\s+into\s+one)\b")


def check_jargon(masked: str) -> list[Finding]:
    """§1.6, for chat only.

    Deliverables are exempt on purpose: a document written for someone else may
    need the domain's own words, and §1.6 governs what reaches Alex. This runs
    from `chat_findings` and from nowhere else.
    """
    found: list[Finding] = []
    seen: set[str] = set()
    for pattern, what in JARGON:
        for m in pattern.finditer(masked):
            word = m.group(0)
            if JARGON_OK.search(word) or word.lower() in seen:
                continue
            seen.add(word.lower())
            found.append(Finding(BLOCK, "jargon", line_of(masked, m.start()),
                                 f"master §1.6: {word!r} is {what} — it means nothing to Alex. "
                                 f"Say what happened and what it means for him."))
    return found


def chat_findings(text: str, vocab: dict) -> list[Finding]:
    """What the chat gate checks. Named so a test can reach it.

    The cap lived inline at the call site and was §7.8's three rather than
    §1.3a's two — the gate ran one notch looser than the rule it cited, from the
    day it shipped until 2026-08-13. A test that calls check_structure directly
    cannot catch that; it has to go through whatever run_stop actually uses.
    """
    masked = mask(text)
    return (check_vocabulary(text, masked, vocab)
            + check_structure(masked, CHAT_PROSE_CAP)
            + check_jargon(masked))


def run_stop() -> int:
    """Stop-hook mode: check what this turn said to Alex before it reaches him.

    Chat is the one surface the Write/Edit hook never sees. This closes it.

    Blocks by returning `{"decision": "block"}` so the turn continues and the
    message is rewritten. Exactly one retry: `stop_hook_active` is honoured, so
    a second pass never blocks. A rewrite loop with no cap is the shape master
    §13.4 bans and `field-notes.md` §1 already recorded at 55 cycles.

    Anything that goes wrong prints a systemMessage and exits 0. A chat check
    that cannot run must say so, never pass silently.
    """
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        print(json.dumps({"systemMessage": "chat check did not run: unreadable hook payload"}))
        return 0

    if payload.get("stop_hook_active"):
        return 0  # one retry only

    transcript = payload.get("transcript_path")
    if not transcript:
        print(json.dumps({"systemMessage":
                          "chat check did not run: the hook payload carried no transcript_path"}))
        return 0

    blocks, error = _turn_text(transcript)
    if error:
        print(json.dumps({"systemMessage": f"chat check did not run: {error}"}))
        return 0
    if not blocks:
        return 0  # a turn that said nothing to Alex, e.g. tool calls only

    root = find_repo_root(Path.cwd())
    vocab = load_vocabulary(root)
    thin = [name for name, least in VOCAB_FLOOR.items() if len(vocab[name]) < least]
    if thin:
        print(json.dumps({"systemMessage":
                          f"chat check ran without §2: the writing-standards skill loaded "
                          f"short ({', '.join(thin)}). Run predelivery.py --selftest."}))
        return 0

    # Only the last block can still be changed. A turn ends with everything it
    # said still in the transcript, so checking all of it re-reports findings in
    # narration Alex read twenty tool calls ago — text a rewrite cannot touch.
    # Measured 2026-08-18: seventeen blocks in one turn, and the block message
    # carried findings from eleven of them, none of them fixable. A gate that
    # asks for the impossible is a gate that gets ignored.
    #
    # §1.3a, not §7.8: anything addressed to Alex directly caps at two
    # consecutive sentences. The gate had been set one notch looser than the
    # rule it enforces since it shipped.
    findings = [f for f in chat_findings(blocks[-1], vocab) if f.severity == BLOCK]
    # Earlier blocks are still checked, and still reported — as context, never as
    # the reason for the block. What they buy is the count: a turn that narrated
    # badly and then wrote a clean final message should say so, not read clean.
    earlier = []
    for text in blocks[:-1]:
        earlier += [f for f in chat_findings(text, vocab) if f.severity == BLOCK]
    if not findings:
        if earlier:
            print(json.dumps({"systemMessage":
                              "chat check: the message just sent is clean, but %d break(s) "
                              "went out earlier in this turn and cannot now be rewritten. "
                              "They are the ones worth not repeating." % len(earlier)}))
        return 0

    lines = []
    for finding in findings:
        if finding.rule == "paragraph":
            # Splitting the paragraph clears the check and manufactures §7.10's
            # first tell — every sentence the same middling length. Name the
            # actual fix so the gate cannot be satisfied by making the prose
            # worse.
            lines.append(f"- {finding.message} Restructure it as a list or a table. "
                         f"Do NOT satisfy this by chopping it into shorter paragraphs — "
                         f"that manufactures the uniform rhythm §7.10 bans.")
        else:
            lines.append(f"- {finding.message}")

    print(json.dumps({
        "decision": "block",
        "reason": "The message you were about to send breaks rules that are already in force. "
                  "Rewrite it and send again:\n" + "\n".join(lines),
    }))
    return 0


def run_text(path_name: str) -> int:
    """Check a block of prose that is not a deliverable file.

    Used for chat replies and for pasted output handed to the audit loop
    (master §13). Filename form, acronym glossing and the ledger gate all key
    off a real deliverable path, so they are skipped here rather than fired
    against a scratch file and reported as findings that mean nothing.

    Prints one JSON object so a harness can read it. Exit is 1 when anything
    blocking was found, 0 otherwise — including when the text is empty, which
    is reported rather than passed off as clean.
    """
    import json

    path = Path(path_name)
    content = read_text(path)
    if content is None:
        print(json.dumps({"error": f"cannot read {path_name}", "findings": []}))
        return 1
    if not content.strip():
        print(json.dumps({"error": "text is empty — nothing was checked", "findings": []}))
        return 1

    root = find_repo_root(path.parent.resolve()) or find_repo_root(Path.cwd())
    vocab = load_vocabulary(root)
    thin = [name for name, least in VOCAB_FLOOR.items() if len(vocab[name]) < least]
    masked = mask(content)
    findings = check_vocabulary(content, masked, vocab) + check_structure(masked)

    payload = {
        "words": len(content.split()),
        "blocking": sum(1 for f in findings if f.severity == BLOCK),
        "warnings": sum(1 for f in findings if f.severity != BLOCK),
        "vocabulary_lists_short": thin,
        "findings": [
            {
                "severity": "block" if f.severity == BLOCK else "warn",
                "rule": f.rule,
                "line": f.line,
                "message": f.message,
            }
            for f in findings
        ],
    }
    print(json.dumps(payload, indent=1))
    # A short vocabulary load means §2 went partly unchecked; that is a failure
    # of the check, not a pass, so it must not exit 0.
    return 1 if payload["blocking"] or thin else 0


def run_files(paths: list[str]) -> int:
    worst = 0
    for name in paths:
        path = Path(name)
        content = read_text(path)
        if content is None:
            print(f"{name}: cannot read", file=sys.stderr)
            worst = max(worst, 1)
            continue
        root = find_repo_root(path.parent.resolve())
        findings = check(path, content, root)
        rel = relative(path, root)
        if not findings:
            print(f"ok   {rel}")
            continue
        blocking = [f for f in findings if f.severity == BLOCK]
        print(f"{'FAIL' if blocking else 'warn'} {rel}")
        for finding in findings:
            marker = "BLOCK" if finding.severity == BLOCK else " warn"
            print(f"  {marker}{finding.render(rel)[1:]}")
        if blocking:
            worst = 1
    return worst


def _drive_stop(payload) -> str:
    """Run the Stop gate the way the harness does: JSON on stdin."""
    import io
    import json as _json
    from contextlib import redirect_stdout
    saved = sys.stdin
    sys.stdin = io.StringIO(_json.dumps(payload))
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            run_stop()
    except SystemExit:
        pass
    finally:
        sys.stdin = saved
    return buffer.getvalue()


def _drive_hook(payload) -> str:
    """Run the PostToolUse gate exactly as the harness does: JSON on stdin.

    Calling check() in a test cannot tell a working gate from one whose payload
    parsing returns None — the suite stayed green with the gate stubbed out.
    """
    import io
    import json as _json
    from contextlib import redirect_stdout
    saved = sys.stdin
    sys.stdin = io.StringIO(_json.dumps(payload))
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            run_hook()
    finally:
        sys.stdin = saved
    return buffer.getvalue()


def run_selftest() -> int:
    """Confirm the rules actually loaded. A silent empty load checks nothing."""
    vocab = load_vocabulary(find_repo_root(Path(__file__).resolve().parent))
    ok = True
    for name, want in VOCAB_FLOOR.items():
        got = len(vocab[name])
        status = "ok" if got >= want else "LOW"
        if got < want:
            ok = False
        print(f"  {status:3} {name:9} {got:>3} (expected at least {want})")
    if not ok:
        print("predelivery selftest FAILED: the writing-standards skill did not load "
              "or its sections have moved. Vocabulary enforcement is off.", file=sys.stderr)
        return 1

    # Six entries were list entries that could never fire: alternatives packed
    # into one quoted head ("serves as / stands as / …"), an ellipsis standing
    # for the writer's own words, and a placeholder opening the phrase. Each is
    # checked here against a sentence someone would actually write.
    #
    # NOT by feeding the stored phrase back in — that probe matches its own
    # literal and reports all 57 live, including the six dead ones.
    for sentence in ("Ever wondered why the numbers moved?",
                     "What if I told you the model is wrong?",
                     "In a world where capital is scarce, this matters.",
                     "The result serves as proof.",
                     "This stands as the best option.",
                     "No hedging. No caveats. Just the number.",
                     "The checker — not the rules — is the gate here."):
        if not check_vocabulary(sentence, mask(sentence), vocab):
            print("predelivery selftest FAILED: a banned construction was not caught: "
                  "%r. A phrase's notation is not reaching the matcher." % sentence,
                  file=sys.stderr)
            return 1
    # And the same machinery must leave ordinary prose alone.
    for sentence in ("The gap is five inches wide.",
                     "We shipped the fix and measured it."):
        if check_vocabulary(sentence, mask(sentence), vocab):
            print("predelivery selftest FAILED: clean prose was flagged: %r" % sentence,
                  file=sys.stderr)
            return 1
    # Alternatives must be split at load, or one entry silently stands for three.
    unsplit = [p for p, _s in vocab["phrases"] if " / " in p]
    if unsplit:
        print("predelivery selftest FAILED: %d phrase(s) still pack alternatives into "
              "one entry: %s" % (len(unsplit), ", ".join(repr(p) for p in unsplit[:5])),
              file=sys.stderr)
        return 1

    # A loaded list proves nothing about whether the rules fire. Each case below
    # is text the checker must catch or must leave alone. The two marked
    # `regression` reproduce bugs that shipped and went unnoticed.
    def findings_for(text: str) -> list[Finding]:
        masked = mask(text)
        return check_vocabulary(text, masked, vocab) + check_structure(masked)

    def rules_in(text: str) -> set[str]:
        return {f.rule for f in findings_for(text)}

    cases = [
        ("banned word", "We should utilize the approach.", "banned-word", True),
        ("banned phrase", "Great question! Here is the answer.", "banned-phrase", True),
        ("banned opener", "The plan works. Furthermore, it is cheap.", "banned-opener", True),
        ("litotes", "The result is not bad.", "litotes", True),
        ("four-sentence paragraph",
         "One sentence here. Two sentences here. Three sentences here. Four sentences here.",
         "paragraph", True),
        ("question heading", "## Why does this fail?\n\nBody text.", "heading", True),
        ("closer", "The finding stands.\n\nI hope this helps.", "closer", True),
        ("clean prose is left alone", "- A short bullet.\n- Another one.", None, False),
        ("banned word inside a code fence is exempt",
         "Body text here.\n\n```\nutilize this\n```\n", "banned-word", False),
        # regression, 2026-08-13: the placeholder substitution ran on the
        # lowercased pattern while looking for an uppercase X, so all twelve
        # placeholder phrases were byte-identical to literals and never matched.
        ("regression: placeholder phrase fires",
         "It falls down when it comes to pricing.", "banned-phrase", True),
        # regression, 2026-08-13: the quote scan read the unmasked text, so an
        # odd number of quotes inside a fence shifted every pair after it and
        # left banned words inside a real citation exposed to the checker.
        ("imperative heading", "## Design for the machine path\n\nBody.", "heading", True),
        ("imperative heading, numbered", "## 3. Close the loop\n\nBody.", "heading", True),
        # The second token is what separates an instruction from a noun phrase
        # that happens to start with the same word.
        ("noun phrase starting with a verb word", "## Design decisions\n\nBody.", "heading", False),
        ("regression: odd quote in a fence does not expose a citation",
         '```sh\nsed \'s/"//\' f.txt\n```\n\nIt states: "The fee is a holistic two percent."\n',
         "banned-word", False),
    ]

    # regression, 2026-08-13: three defects an expert panel reproduced, each
    # letting a rule that was written and deployed go unenforced.
    extra = []

    # The chat gate cited §1.3a — two consecutive sentences — and ran §7.8's
    # three, so it was one notch looser than the rule it named, since it shipped.
    two = "This is one sentence. This is a second sentence."
    # Through chat_findings, which is what run_stop calls — a test against
    # check_structure directly passes whatever the gate is wired to.
    if not [f for f in chat_findings(two + " And a third.", vocab) if f.rule == "paragraph"]:
        extra.append("chat cap: three sentences to Alex must block at §1.3a's cap of two")
    if [f for f in chat_findings(two, vocab) if f.rule == "paragraph"]:
        extra.append("chat cap: two sentences is the cap, not a break")
    if check_structure(mask(two + " And a third."), FILE_PROSE_CAP):
        extra.append("file cap: three sentences is fine in a file under §7.8")
    if (CHAT_PROSE_CAP, FILE_PROSE_CAP) != (2, 3):
        extra.append("caps: §1.3a is two and §7.8 is three")

    # A new break of a class the file already carried was demoted to a warning,
    # because two four-sentence paragraphs produced identical messages.
    old = "One. Two. Three. Four."
    new = old + "\n\nAlpha here. Beta here. Gamma here. Delta here."
    before = check_structure(mask(old))
    after = check_structure(mask(new))
    if len({f.span for f in after}) != 2:
        extra.append("demotion: two different paragraphs must carry different spans, or the "
                     "second demotes to a warning behind the first")
    prior = {(f.rule, f.message, f.span) for f in before}
    fresh = [f for f in after if (f.rule, f.message, f.span) not in prior]
    if len(fresh) != 1:
        extra.append("demotion: a second, different four-sentence paragraph must stay a block "
                     "(got %d new finding(s))" % len(fresh))

    # The 200-word cap is on the CLAUDE.md this system installs, and that file
    # lives in the target repos — the only place the check did not run.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        (target / ".claude").mkdir()
        big = "word " * 260
        if not check_budget(target / "CLAUDE.md", "@.claude/universal.md\n\n" + big, target):
            extra.append("budget: the bundle's CLAUDE.md is uncapped outside the home repo")
        if check_budget(target / "CLAUDE.md", big, target):
            extra.append("budget: a repo's own CLAUDE.md is flagged, never blocked (§5.1)")

    # A term on a continuation line must be loaded. Returning on the first line
    # of a block meant such a term was in the rules and enforced by nothing.
    two_lines = "alpha, beta\ngamma, delta — with a note\n"
    got = comma_words(two_lines) if "comma_words" in dir() else None
    if got is not None and "gamma" not in got:
        extra.append("vocabulary: a term on a continuation line is not loaded")

    # The quote mask, both directions. One unpaired straight quote used to shift
    # every pair after it: `The gap is 5" wide...` hid three banned words, and
    # the reverse scanned words inside a §4 citation that §2 exempts. Driven
    # through chat_findings, the function the Stop gate actually calls.
    mask_cases = [
        ('an inch-mark must not hide banned prose',
         'The gap is 5" wide. This holistic approach delves into utilize territory per "x".',
         True),
        ('the same prose without it still fires',
         'The gap is 5 inches wide. This holistic approach delves into utilize territory.',
         True),
        ('banned words inside a quotation stay exempt',
         'He wrote: "this holistic approach will delve into how we utilize it".', False),
        ('clean prose is left alone',
         'The gap is five inches wide and the memo says so.', False),
    ]
    mask_cases += [
        # One stray inline fence plus a real block below it: greedy pairing
        # matched the stray with the block's OPENING fence and blanked the
        # prose between them, exempting it from every check.
        ('a stray inline fence must not pair with a later real one',
         'Write ``` inline here.\n\nThis holistic approach delves into utilize land.\n\n'
         '```\ncode\n```\n', True),
        ('a real fenced block stays exempt',
         '```\nholistic delve utilize\n```\n', False),
        ('prose after a real fenced block is still checked',
         '```\ncode\n```\n\nThis holistic approach delves into utilize land.', True),
        # A three-backtick fence nested inside a four-backtick one. The regex
        # form paired the outer OPENER with the inner OPENER and left the inner
        # block exposed to every check. Measured on real traffic 2026-08-18:
        # two of the sixty-one plain-speech hits since the check shipped were
        # this, in a document quoted into chat because Alex asked for it.
        ('a fence nested inside a longer fence stays exempt',
         '````markdown\n# Doc\n\n```\nholistic delve utilize\n```\n\nfine here.\n````\n',
         False),
        ('a longer fence closes only on a run at least as long',
         '````\ncode\n```\nstill code\n````\n\nThis holistic approach delves into utilize.',
         True),
        # The docstring has claimed this since audit round two and nothing
        # tested it: breaking it left the suite green (calibration, 2026-08-18).
        ('an unclosed fence runs to the end rather than exposing what follows',
         'text before\n\n```\nholistic delve utilize\n', False),
    ]
    for name, text, want in mask_cases:
        if bool([f for f in chat_findings(text, vocab) if "§2" in f.message]) != want:
            extra.append("quote mask: %s" % name)

    # A closing quote used to blank one character past itself, eating the
    # sentence terminator, so two sentences counted as one and the §1.3a cap
    # ran loose after any quotation.
    # A sentence may open lower-case; requiring a capital collapsed a whole
    # paragraph to one and the cap never fired on it.
    # Counted exactly, both ways: requiring a capital under-counted a lower-case
    # paragraph to one; allowing anything made every unlisted abbreviation a
    # sentence end and blocked messages already inside the cap.
    for sample, want in [
            ("We met Dr. Smith at 3 p.m. today. We left.", 2),
            ("The U.K. team signed. That is done.", 2),
            ("one here. two follow now. three is plenty. four is too many.", 4),
            ("One here. Two follow. Three is plenty.", 3),
            ("The rate is 3.5 percent this year.", 1),
            ("The run costs 3 vs. 4 units and that is all.", 1)]:
        got = count_sentences(sample)
        if got != want:
            extra.append("sentence count: %r counted %d, wanted %d" % (sample[:40], got, want))

    for label, sample, want in [
            ("lower-case sentence starts still count",
             "one here. two follow now. three is plenty. four is too many.", True),
            ("an abbreviation does not end a sentence",
             "We met Dr. Smith at 3 p.m. today.", False),
            ("a decimal does not end one either",
             "The rate is 3.5 percent this year.", False)]:
        if bool([f for f in chat_findings(sample, vocab) if "1.3a" in f.message]) != want:
            extra.append("sentence count: %s" % label)

    quoted = 'He said "yes". Then he left. Then he came back.'
    counted = [f for f in chat_findings(quoted, vocab) if "1.3a" in f.message]
    if not counted or "has 3" not in counted[0].message:
        extra.append("sentence count: a quotation must not swallow the terminator after it "
                     "(got %r)" % (counted[0].message if counted else "no finding"))

    # The gate itself, end to end, on the payload shape the harness sends. The
    # suite could not tell a working write-gate from one returning nothing:
    # stubbing check() to [] left it green while the hook shipped dead to 11
    # repos (audit, 2026-08-17).
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "note.md"
        payload = {"tool_name": "Write", "tool_input": {
            "file_path": str(doc),
            "content": "# Note\n\nThis holistic approach will delve into how we utilize it.\n"}}
        spoken = _drive_hook(payload)
        if "deny" not in spoken:
            extra.append("write gate: a Write carrying banned vocabulary was not denied "
                         "(got %r)" % spoken[:120])
        clean = {"tool_name": "Write", "tool_input": {
            "file_path": str(doc), "content": "# Note\n\nThe gap is five inches wide.\n"}}
        if "deny" in _drive_hook(clean):
            extra.append("write gate: clean prose was denied")

    # The capture store is exempt, driven through the gate rather than by
    # calling is_capture_file(). Alex's own words are not Claude's prose, and a
    # session is forbidden to edit them, so a finding there is unfixable work.
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        (home / "memory" / "inbox").mkdir(parents=True)
        (home / ".git").mkdir()          # what find_repo_root actually looks for
        (home / "memory" / "map.md").write_text("# Memory map\n", encoding="utf-8")
        wordy = ("> a quote\nabout: One sentence. A second sentence. A third sentence. "
                 "A fourth sentence lands here.\n")
        capture = home / "memory" / "inbox" / "2026-08-13.md"
        spoken = _drive_hook({"tool_name": "Write", "tool_input": {
            "file_path": str(capture), "content": "# Feedback\n\n" + wordy}})
        if "deny" in spoken or "paragraph" in spoken:
            extra.append("capture store: a verbatim record was checked as Claude's prose "
                         "(got %r)" % spoken[:140])
        # The exemption is the inbox, not all of memory/ — a node is authored.
        node = home / "memory" / "claude-improvement.md"
        spoken = _drive_hook({"tool_name": "Write", "tool_input": {
            "file_path": str(node), "content": "# Domain\n\n" + wordy}})
        if "paragraph" not in spoken:
            extra.append("capture store: the exemption leaked to an authored domain file "
                         "(got %r)" % spoken[:140])

    # The Stop gate, end to end. run_stop() and _turn_text() had no test at
    # all: the chat check could be stubbed to nothing and the suite stayed
    # green while every message shipped unchecked (audit round three).
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "transcript.jsonl"
        import json as _j
        bad = ("One sentence here. A second sentence follows. And a third one lands. "
               "A fourth for good measure.")
        log.write_text(
            _j.dumps({"type": "user", "message": {"content": "hello"}}) + "\n" +
            _j.dumps({"type": "assistant",
                      "message": {"content": [{"type": "text", "text": bad}]}}) + "\n",
            encoding="utf-8")
        spoken = _drive_stop({"transcript_path": str(log)})
        if "1.3a" not in spoken:
            extra.append("chat gate: a four-sentence paragraph was not blocked (got %r)"
                         % spoken[:140])
        log.write_text(
            _j.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "- one\n- two\n- three"}]}}) + "\n",
            encoding="utf-8")
        if "1.3a" in _drive_stop({"transcript_path": str(log)}):
            extra.append("chat gate: a clean list was blocked")

        # A long turn is the one most worth checking, and the gate used to read
        # only the last 256 KB of the transcript — so text written before a big
        # tool result in the same turn shipped unchecked. The bulk here is one
        # tool_result larger than that old window, sitting between the break and
        # the end of the file.
        # The turn is read whole, not through a tail window. Asserted on
        # _turn_text rather than through the gate: the gate now blocks on the
        # last block alone, so a window that drops earlier ones is invisible
        # from outside. What broke was the reading, so the reading is the test.
        bulk = "x" * (300 * 1024)
        log.write_text(
            _j.dumps({"type": "user", "message": {"content": "go"}}) + "\n" +
            _j.dumps({"type": "assistant",
                      "message": {"content": [{"type": "text", "text": bad}]}}) + "\n" +
            _j.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "content": bulk}]}}) + "\n" +
            _j.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "- one\n- two"}]}}) + "\n",
            encoding="utf-8")
        seen_blocks, read_error = _turn_text(str(log))
        if read_error or len(seen_blocks) != 2 or bad not in seen_blocks[0]:
            extra.append("chat gate: text written before a 300 KB tool result was not read "
                         "back — the turn is being read through a tail window (got %d block(s), "
                         "error %r)" % (len(seen_blocks), read_error))
        # And the gate blocks on the last block, which is the only one a rewrite
        # can still change.
        log.write_text(
            _j.dumps({"type": "user", "message": {"content": "go"}}) + "\n" +
            _j.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "- one\n- two"}]}}) + "\n" +
            _j.dumps({"type": "assistant",
                      "message": {"content": [{"type": "text", "text": bad}]}}) + "\n",
            encoding="utf-8")
        if "1.3a" not in _drive_stop({"transcript_path": str(log)}):
            extra.append("chat gate: a break in the final message was not blocked")
        # A break in an earlier block, with a clean final message, does not block
        # — it cannot be rewritten — but it is still reported.
        log.write_text(
            _j.dumps({"type": "user", "message": {"content": "go"}}) + "\n" +
            _j.dumps({"type": "assistant",
                      "message": {"content": [{"type": "text", "text": bad}]}}) + "\n" +
            _j.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "- one\n- two"}]}}) + "\n",
            encoding="utf-8")
        spoken = _drive_stop({"transcript_path": str(log)})
        if "block" in spoken:
            extra.append("chat gate: blocked on text a rewrite cannot reach")
        if "earlier in this turn" not in spoken:
            extra.append("chat gate: an earlier break went unreported (got %r)" % spoken[:120])

        # §1.6, the plain-English rule, which nothing enforced until Alex said
        # the conversation "looks alien" for the third time. Driven through the
        # Stop gate, not by calling check_jargon, because the point is that it
        # reaches chat and only chat.
        for said, why in (("I pushed the fix to the branch and merged the pull request.", "git"),
                          ("That is recorded as CI-042 in the graph.", "a node id"),
                          ("Master §1.6 covers this.", "a § number"),
                          ("The selftest passed and stdout was empty.", "machine words")):
            log.write_text(
                _j.dumps({"type": "user", "message": {"content": "hi"}}) + "\n" +
                _j.dumps({"type": "assistant",
                          "message": {"content": [{"type": "text", "text": said}]}}) + "\n",
                encoding="utf-8")
            if "1.6" not in _drive_stop({"transcript_path": str(log)}):
                extra.append("chat gate: %s reached Alex unflagged (%r)" % (why, said))
        plain = "I fixed the thing you asked about and checked it works."
        log.write_text(
            _j.dumps({"type": "user", "message": {"content": "hi"}}) + "\n" +
            _j.dumps({"type": "assistant",
                      "message": {"content": [{"type": "text", "text": plain}]}}) + "\n",
            encoding="utf-8")
        if "1.6" in _drive_stop({"transcript_path": str(log)}):
            extra.append("chat gate: plain words were flagged as jargon")

    # A deliverable is exempt: §1.6 governs what reaches Alex, and a document
    # written for someone else may need the domain's own words.
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "note.md"
        spoken = _drive_hook({"tool_name": "Write", "tool_input": {
            "file_path": str(doc),
            "content": "# Note\n\nRun the selftest, then merge the pull request.\n"}})
        if "1.6" in spoken:
            extra.append("write gate: the plain-English rule leaked onto a deliverable")

    for line in extra:
        print(f"  FAIL {line}")
    if extra:
        return 1

    behaviour_ok = True
    for name, text, rule, want in cases:
        got = rule in rules_in(text) if rule else bool(findings_for(text))
        if got != want:
            behaviour_ok = False
            print(f"  FAIL {name}: expected {rule or 'any finding'} present={want}, got {got}")
    if not behaviour_ok:
        print("predelivery selftest FAILED: rules loaded but did not fire as expected.",
              file=sys.stderr)
        return 1

    print(f"predelivery selftest passed ({len(VOCAB_FLOOR)} list floors, {len(cases)} behaviours)")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--hook":
        return run_hook()
    if args and args[0] == "--selftest":
        return run_selftest()
    if args and args[0] == "--stop":
        return run_stop()
    if args and args[0] == "--text":
        if len(args) < 2:
            print("--text needs a file holding the prose to check", file=sys.stderr)
            return 1
        return run_text(args[1])
    if not args:
        print(__doc__)
        return 0
    return run_files(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # fail open: never wedge a session
        if "--hook" in sys.argv:
            # Fail open, but never in silence: a crash that reads as a clean
            # pass is the failure mode this whole checker exists to avoid.
            print(json.dumps({"systemMessage":
                              f"pre-delivery check crashed ({exc!r}) — enforcement is off "
                              f"for this write (master §9.5)"}))
            sys.exit(0)
        print(f"predelivery: internal error: {exc}", file=sys.stderr)
        # A crash in --selftest must fail. Failing open belongs to the hook,
        # where blocking a write on our own bug costs more than the check is
        # worth; a test run that crashes and exits 0 makes its CI step
        # incapable of failing (audit round three).
        sys.exit(1 if "--selftest" in sys.argv else 0)
