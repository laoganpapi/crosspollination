#!/usr/bin/env python3
"""Capture what Alex says, before any model decides whether it mattered.

Usage:
    python3 .claude/hooks/feedback.py --capture   UserPromptSubmit: record the turn
    python3 .claude/hooks/feedback.py --report    unpromoted records, one line each
    python3 .claude/hooks/feedback.py --sweep     Stop: record what the prompt hook missed
    python3 .claude/hooks/feedback.py --selftest  run the built-in tests

Why this exists. Every correction in the graph reached it because a session chose
to write a node. That mechanism is measured, and it fails: CI-014, CI-015 and
CI-036 are three separate enactments of one correction, and CI-036 records the
rule being broken hours after it was written down twice. A rule cannot fix a
defect whose mechanism is a session not remembering.

So capture is mechanical and unconditional. The hook holds Alex's raw text in a
shell process before the model sees it, and writes it. It classifies nothing,
because a detector built from the obvious signals scored 6 of 7 against the seven
quotes actually in the graph — the miss was "centralize then globalize", two bare
words that produced two nodes and a shipped mechanism. A gate on detection loses
one correction in seven, silently and permanently. The signals are recorded as a
label to sort by, never as a condition on writing.

Judgement stays where judgement belongs: turning a record into a graph node needs
a diagnosis, and that is a session's job. What the session cannot do is forget —
an unpromoted record is reported at the start of every session until it is dealt
with, by `validate.py --open` reading this directory.

Failure behaviour: every path exits 0. A capture hook that blocks a prompt on its
own bug would cost more than the feedback it protects. When it cannot write, it
says so in a systemMessage rather than passing silently.
"""

import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Home repo: the graph is here, so a record can be promoted in the same session.
# Anywhere else: the session has one repo and no graph (§9.2), so the record
# rides that repo's own commit and is collected later.
HOME_INBOX = "memory/inbox"
AWAY_INBOX = ".claude/feedback"

# Shapes worth sorting by. Never a condition on writing — see the module note.
SIGNALS = [
    ("correction", re.compile(r"\b(don'?t|do not|stop|never|no more|instead of|"
                              r"not what i|that'?s wrong|you were told|i already|"
                              r"quit|undo|revert)\b", re.I)),
    ("preference", re.compile(r"\b(i want|i'?d prefer|i prefer|from now on|going forward|"
                              r"in future|always|only ever|i never want)\b", re.I)),
    ("rejection", re.compile(r"\b(too long|too much|too many|reads badly|this is wrong|"
                             r"nonsense|useless|rubbish|bad output|hate)\b", re.I)),
    ("repetition", re.compile(r"\b(again|still|as i said|i told you|how many times)\b", re.I)),
]


# Not everything arriving on UserPromptSubmit is Alex speaking. A scheduled
# wake, a GitHub event relayed into the session, a slash command's output and a
# system reminder all come through the same field. Found the hour this hook
# shipped: it recorded a PR-subscription wake as feedback, and an unpromoted
# record is reported at every session start until someone writes it up — so a
# false positive here is not noise, it is a standing instruction to write up
# something Alex never said.
#
# predelivery.py excludes the same class from the other direction (a tool result
# is a user entry and is not Alex); this is the prompt-side half of that test.
RECORD_HEAD = re.compile(r"^## (fb-\d{4}-\d{2}-\d{2}-[0-9a-f]{10})\s*$")

MACHINE = re.compile(
    r"^\s*(<wake\b|<event\b|<system-reminder>|<task-notification>|<command-name>|"
    r"<local-command-stdout>|<untrusted_external_data|\[SYSTEM NOTIFICATION|"
    # The harness writes these into the transcript as user entries. They are not
    # Alex: the first is a compaction summary written by another pass, the second
    # a marker the interface inserts. Both were swept as things he said.
    r"This session is being continued from a previous conversation|"
    # The harness sends this as an ordinary prompt when it resumes a session
    # after a limit reset or an interrupt. It reached the store three times,
    # once at `seen: 6` — a record claiming Alex repeated an instruction six
    # times in a day he never said it once. The graph named the string as
    # harness text on 2026-08-17 and it recurred on 2026-08-18, because naming
    # it was not the same as adding it here (panel round 2).
    r"(?:please\s+)?continue from where you left off|"
    r"\[Request interrupted by user)",
    re.I)


def today_utc():
    """The day, on the same clock the transcript stamps.

    `date.today()` is the machine's LOCAL calendar date, and every transcript
    entry is stamped UTC. For any machine not on UTC there is a window every day
    where the two disagree — and the day is baked into a record's id and into
    the sweep's key, so one message became two records under two days, splitting
    the count and making the sweep report a message the prompt hook had recorded
    seconds earlier as never recorded (panel round 4, 2026-08-18).
    """
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def repo_root(start):
    found = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
    if found.returncode == 0 and found.stdout.strip():
        return Path(found.stdout.strip())
    here = Path(start).resolve()
    for candidate in [here, *here.parents]:
        # `memory/map.md` too, and checked at the same level: outside git this
        # walked past a repo carrying the graph and stopped at the first
        # ancestor with any `.claude` directory — including a stray one in a
        # temp root — so captures landed outside the repo entirely (audit round
        # three).
        if (candidate / "memory" / "map.md").is_file() or (candidate / ".claude").is_dir():
            return candidate
    return here


def inbox(root):
    """Where records land, and whether this repo holds the graph."""
    home = (root / "memory" / "map.md").is_file()
    return root / (HOME_INBOX if home else AWAY_INBOX), home


def origin(root):
    """The remote, with any embedded credential removed.

    This goes verbatim into a record that is committed and later harvested. A
    remote of the form `https://user:token@github.com/...` — which the deploy
    and harvest paths themselves once used — would have written the token into
    a file in the repo (audit round three).
    """
    found = subprocess.run(["git", "-C", str(root), "remote", "get-url", "origin"],
                           capture_output=True, text=True)
    if found.returncode != 0:
        return "(no remote)"
    return re.sub(r"(https?://)[^/@\s]*@", r"\1", found.stdout.strip())


def branch(root):
    found = subprocess.run(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, text=True)
    return found.stdout.strip() if found.returncode == 0 else "(no branch)"


def normalise(text):
    return " ".join(re.sub(r"[^\w\s]", "", text.lower()).split())


def record_id(text, day, where="", asked=""):
    """Per occurrence per day per repo, not per text.

    Keying on the text alone and skipping a repeat would collapse the one signal
    the graph is built on: a correction Alex has to give twice is worse than one
    he gives once, and the count is the evidence.

    The repo is in the key because the harvest merges records from every repo by
    id. Without it, the same words on the same day in two repos collapsed to one
    record and the losing repo's origin, count and context were discarded — and
    "stop doing that" on one day across two repos is exactly the case the count
    exists to measure (audit, 2026-08-17).
    """
    # The RAW text in the key, not just the normalised form. Normalising strips
    # punctuation, so "stop." and "stop!" hashed the same and the second
    # prompt's exact words were never stored (audit round three).
    # `asked` carries a picker's question, and only a picker's. Two decisions
    # answered with the same option text on the same day are two records, and
    # without it the second collided with the first and was dropped — leaving
    # the survivor's `about:` naming the wrong question (panel round 3,
    # 2026-08-18).
    #
    # Appended ONLY when it is non-empty. Adding an empty component still
    # changes the hash, so every id in the store moved and a re-sweep brought
    # back the one entry Alex had ordered removed — its quote had been replaced,
    # so it matched on neither text nor id. Caught by running the sweep against
    # the real store before committing.
    seed = normalise(text) + "\x00" + text + "\x00" + (where or "")
    if asked:
        seed += "\x00" + asked
    # surrogatepass, so an id can always be computed. An unpaired surrogate
    # raised here — before the writer's own tolerant encoder saw anything — and
    # the turn was dropped entirely (audit round four).
    return "fb-%s-%s" % (day, hashlib.sha1(
        seed.encode("utf-8", "surrogatepass")).hexdigest()[:10])


SECRETS = [
    (re.compile(r"\bgh[pusor]_[A-Za-z0-9]{20,}"), "[redacted: github token]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "[redacted: github token]"),
    (re.compile(r"\bsk-[A-Za-z0-9\-_]{20,}"), "[redacted: api key]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "[redacted: slack token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[redacted: aws key id]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
     "[redacted: private key]"),
    (re.compile(r"(https?://)[^/\s:]+:[^/\s@]+@"), r"\1[redacted]@"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
     "[redacted: token]"),
]


def redact(text):
    """Take recognisable credentials out before anything is stored.

    A capture is committed to the repo it was typed in and then copied here by
    the harvest, so a token pasted into a prompt would be replicated and kept
    (audit round four). Shape-based and therefore incomplete by construction —
    it catches the common issuers, not everything — but a redaction that misses
    some is strictly better than storing all of them.
    """
    for pattern, replacement in SECRETS:
        text = pattern.sub(replacement, text)
    return text


def signals_in(text):
    return [name for name, pattern in SIGNALS if pattern.search(text)]


def head(text, limit):
    """The opening, cut at a word boundary, marked where it was cut."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit // 2 else cut).rstrip() + " …"


def last_assistant(transcript_path, limit=400):
    """What the feedback is about. Without it, "you did that wrong" is unreadable
    six weeks later.

    The opening, not the tail. This took the last 400 characters and produced
    records reading `about: unts move, and a second copy would drift from the
    first` — a fragment starting mid-word, which is the one failure the field
    exists to prevent. §1.1 puts the answer at the top of a message, so the
    opening is what a correction is answering; the closing picker is not.
    """
    if not transcript_path:
        return ""
    try:
        path = Path(transcript_path)
        if not path.is_file():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    said = ""
    for line in text.splitlines():
        if '"assistant"' not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    said = block.get("text", "") or said
    return head(said, limit)


def day_of(entry, box):
    """The day a message was said, from its own timestamp.

    Dating a swept message "today" is what turned the first run of this into 29
    spurious records: the transcript holds the whole session, de-duplication is
    per day file, and a message already recorded on 13 August got a fresh id
    under 17 August. Recording each one on the day it was said makes the sweep
    idempotent against the store that already exists.
    """
    stamp = entry.get("timestamp") or (box or {}).get("timestamp") or ""
    return stamp[:10] if len(stamp) >= 10 and stamp[4] == "-" else None


# The picker has more than one wording, and anchoring on one of them threw the
# other away: eleven answers across five days, four of which exist nowhere in
# this repo. "The user answered:" is the shape that carries text Alex typed
# himself rather than an option Claude wrote — his free-text redirects, which
# are the answers worth most (panel round 1, 2026-08-18). The trailing
# boilerplate differs between the two and is simply not required.
ANSWERED = re.compile(
    r"^(?:Your questions have been answered|The user answered):\s*(.*?)\s*"
    r"(?:(?:You can now continue with these answers in mind|"
    r"Read the answers carefully)\b.*)?$", re.S)
ANSWER_PAIR = re.compile(r'"([^"]+)"\s*=\s*"([^"]*)"')


def picker_answers(content):
    """Alex's answers to a picker, which arrive as a tool result rather than as
    a message he typed.

    Every turn ending on a decision ends on a picker (§1.3b), so the picker is
    where most of his decisions are made — and none of them reached the store.
    Nineteen went past in this session's transcript across five days, among them
    "Land all twelve and raise the cap" and "Remove that entry entirely". The
    hole is the same one mid-turn messages had: the entry is in the transcript
    and the capture path was not looking at that shape.

    The quote stored is his answer; the question is recorded as what it was
    about, so a reader can never mistake one for the other. Anchored at the
    start of the result, because a shell command that printed the phrase is a
    tool result too.
    """
    out = []
    for block in content:
        if not (isinstance(block, dict) and block.get("type") == "tool_result"):
            continue
        body = block.get("content")
        if isinstance(body, list):
            body = "".join(part.get("text", "") for part in body
                           if isinstance(part, dict))
        if not isinstance(body, str):
            continue
        answered = ANSWERED.match(body.strip())
        if not answered:
            continue
        for question, answer in ANSWER_PAIR.findall(answered.group(1)):
            answer = answer.strip()
            if answer:
                out.append((answer, "answer to Claude's question — " + question.strip()))
    return out


def turn_messages(transcript_path):
    """Every real thing Alex said in the transcript, oldest first, with the
    reply each one followed.

    `UserPromptSubmit` fires when Alex submits a prompt and starts a turn. A
    message he sends WHILE a turn is running never fires it, so the capture hook
    cannot see it and the record simply has no entry. Measured on this session
    on 2026-08-17: three of eighteen messages were missing, including two
    standing instructions about how work should be run. The store's whole claim
    is that forgetting is not available, and mid-turn messages were the hole in
    it.

    The transcript does hold them, as ordinary user entries, which is why the
    sweep below can put them back.
    """
    if not transcript_path:
        return []
    try:
        path = Path(transcript_path)
        if not path.is_file():
            return []
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    said, out = "", []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        kind = entry.get("type")
        content = (entry.get("message") or {}).get("content")
        # A message sent while a turn is running is queued, and arrives as an
        # `attachment` entry rather than a `user` one — which is precisely why
        # `UserPromptSubmit` never fires for it. The entry marks its own origin,
        # so a human message is told apart from the 59 task notifications in
        # this session's transcript without guessing from the text.
        if kind == "attachment":
            box = entry.get("attachment") or {}
            if box.get("type") != "queued_command":
                continue
            origin_kind = (entry.get("origin") or box.get("origin") or {}).get("kind")
            queued = (box.get("prompt") or "").strip()
            if not queued or MACHINE.match(queued):
                continue
            if origin_kind in (None, "human"):
                out.append((queued, head(said, 400), day_of(entry, box)))
            continue
        if kind == "assistant" and not entry.get("isSidechain"):
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        said = block.get("text", "") or said
            continue
        if kind != "user" or entry.get("isSidechain") or entry.get("isMeta"):
            continue
        if isinstance(content, list):
            # A tool result arrives as a user entry and is not Alex speaking —
            # except when it carries a picker answer, which is him choosing.
            picked = picker_answers(content)
            if picked:
                for answer, asked in picked:
                    out.append((answer, asked, day_of(entry, None)))
                continue
            if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                continue
            text = "\n".join(b.get("text", "") for b in content
                              if isinstance(b, dict) and b.get("type") == "text")
        else:
            text = content if isinstance(content, str) else ""
        text = (text or "").strip()
        if text and not MACHINE.match(text):
            out.append((text, head(said, 400), day_of(entry, None)))
    return out


PICKER_ABOUT = "answer to Claude's question — "


def about_of(lines):
    for line in lines:
        if line.startswith("about: "):
            return line[7:].strip()
    return ""


def dedup_key(day, home, text, about):
    """What makes two entries the same record.

    A picker answer is identified by the question as well as the words: "Run it
    now (Recommended)" under two different questions is two decisions, and
    keying on the words alone dropped the second while the survivor's `about:`
    named the wrong question. An ordinary message is identified by its words
    alone, so the same instruction repeated in a day is one record with a count
    of two rather than two records (panel round 3, 2026-08-18).
    """
    asked = normalise(about) if about.startswith(PICKER_ABOUT) else ""
    return (day, home, normalise(text), asked)


def where_of(lines):
    """The repo a stored record came from, off its location line.

    A record written here carries this repo's remote; one carried in by the
    harvest carries the repo it was typed in, on its own `from:` line.
    """
    for line in lines:
        if line.startswith("from: "):
            return line[6:].strip()
    for line in lines:
        if " · " in line:
            return line.split(" · ")[0].strip()
    return ""


def sweep(payload, root=None, today=None):
    """Record anything said this session that the store does not already hold.

    Runs at Stop, where the whole turn is on disk. Every message goes through
    `capture`, so redaction, locking and de-duplication are the same code as the
    ordinary path — a message already recorded bumps its `seen` count and writes
    no second entry.
    """
    root = root or repo_root(payload.get("cwd") or os.getcwd())
    fallback = today or today_utc()
    folder, _home = inbox(root)

    def stored():
        """What the store already holds, keyed by the day and the words.

        The id cannot be the key here. `UserPromptSubmit` receives the prompt
        wrapped in context the transcript never stores, so the same message
        hashes differently down the two paths — matching on ids re-recorded
        every message in the store, measured at 34 duplicates on 2026-08-17.

        The day belongs in the key with them. Keyed on words alone across every
        day file, the same words said again on a later day were dropped with no
        record and no count — and the count is the one signal this store exists
        to measure (§3, record_id's own note). `harvested.md` is in this folder
        too, so words typed in another repo silently blocked capture here.
        Picker answers repeat by construction, so it fell hardest on decisions
        (panel round 1, 2026-08-18).
        """
        seen, ids = {}, set()
        if folder.is_dir():
            for day_file in sorted(folder.glob("*.md")):
                body = day_file.read_text(encoding="utf-8", errors="replace")
                for ident, _start, lines in blocks(body):
                    quote = "\n".join(line[2:] if line.startswith("> ") else line[1:]
                                       for line in quote_of(lines))
                    # The day comes off the id, which carries it, rather than
                    # off the filename — a harvested record keeps its own day.
                    # The repo belongs in the key too, for the reason record_id
                    # gives: `harvested.md` sits in this folder, so the same
                    # words on the same day in another repo shadowed the home
                    # record entirely — no entry, no count, no day file. The
                    # docstring above claimed that closed and it was not (panel
                    # round 2, 2026-08-18).
                    day = ident[3:13]
                    seen[dedup_key(day, where_of(lines), quote, about_of(lines))] = \
                        (ident, day_file)
                    ids.add(ident)
        return seen, ids

    home = origin(root)
    already, known_ids = stored()
    added = []
    # How many times each thing was said, so a repeat is COUNTED rather than
    # dropped. The count is set from the transcript rather than incremented, so
    # sweeping the same transcript twice does not inflate it — incrementing is
    # what made a tombstoned record climb once per turn.
    times = {}
    for text, about, said_on in turn_messages(payload.get("transcript_path")):
        times[dedup_key(said_on or fallback, home, redact(text), about)] = \
            times.get(dedup_key(said_on or fallback, home, redact(text), about), 0) + 1

    for text, about, said_on in turn_messages(payload.get("transcript_path")):
        day = said_on or fallback
        key = dedup_key(day, home, redact(text), about)
        if key in already:
            ident, day_file = already[key]
            set_seen(day_file, ident, times.get(key, 1))
            continue
        # The id too, not only the words. A record whose quote was replaced —
        # the one message Alex asked to have removed — no longer matches on
        # text, so every sweep reached `capture`, found the id already there and
        # bumped its `seen` count. No content was ever written back, but the
        # count read as Alex repeating himself once per turn.
        asked = about if about.startswith(PICKER_ABOUT) else ""
        if record_id(text, day, home, asked) in known_ids:
            continue
        one = dict(payload)
        one["prompt"] = text
        path, ident, hits = capture(one, root=root, today=day, about=about)
        if path is not None:
            already[key] = (ident, path)
            set_seen(path, ident, times.get(key, 1))
            added.append((ident, hits))
    return added


def set_seen(day_file, ident, count):
    """Raise a record's `seen:` to a number. Never lower it.

    The sweep reads the whole transcript every turn, so incrementing would climb
    once per turn for something said once — setting it from the transcript's own
    count is what makes a re-sweep idempotent.

    But the store is per day and a transcript is per session. A correction
    repeated on the same day in a SECOND session gives that session's sweep a
    count of one, and assigning it wrote the accumulated count back down. The
    count is the only thing this store measures. install/harvest.py's
    refreshed() already refuses to lower a count for records carried in from
    other repos; this is the same guard on the home repo's own day files (panel
    round 4, 2026-08-18).
    """
    try:
        body = Path(day_file).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    out, inside, changed = [], False, False
    for line in lines_of(body):
        if line.startswith("## "):
            inside = line[3:].strip() == ident
        if inside and line.startswith("seen: "):
            try:
                held = int(line[6:].strip())
            except ValueError:
                held = 0
            want = "seen: %d" % max(count, held)
            changed = changed or line != want
            line = want
        out.append(line)
    if changed:
        write_atomic(Path(day_file), "\n".join(out) + "\n")


def capture(payload, root=None, today=None, about=None):
    """Append one record. Returns (path, id, signals) or (None, reason, [])."""
    text = (payload.get("prompt") or "").strip()
    if not text:
        return None, "no prompt in the payload", []
    if MACHINE.match(text):
        return None, "machine-generated turn, not Alex", []
    root = root or repo_root(payload.get("cwd") or os.getcwd())
    day = today or today_utc()
    folder, _home = inbox(root)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / ("%s.md" % day)
        found = signals_in(text)
        about = last_assistant(payload.get("transcript_path")) if about is None else about
        # Everything slow happens before the lock: two git calls and a
        # transcript read used to sit between the read and the write, and
        # twelve concurrent captures against a fresh repo left four records on
        # disk, all twelve exiting 0 in silence (audit, 2026-08-17).
        where = "%s · %s · %s" % (origin(root), branch(root), day)
        asked = about if (about or "").startswith(PICKER_ABOUT) else ""
        ident = record_id(text, day, origin(root), asked)
        with locked(folder / (".%s.lock" % day)):
            existing = target.read_text(encoding="utf-8") if target.exists() else ""
            if ("## %s" % ident) in existing:
                # Same words, same day: a repeat inside one session. Count it
                # rather than dropping it — recurrence is the measurement.
                write_atomic(target, bump_seen(existing, ident))
                return target, ident, found
            block = [
                "## %s" % ident,
                where,
                "signals: %s" % (", ".join(found) if found else "none"),
                "seen: 1",
                "status: new",
                "",
                "> " + "\n> ".join(lines_of(redact(text))),
                "",
            ]
            if about:
                block[-1:] = ["about: %s" % redact(about), ""]
            header = "" if existing else ("# Feedback captured %s\n\nVerbatim, unclassified, "
                                          "append-only. Promotion to a graph node is a session's "
                                          "job; forgetting is not available.\n\n" % day)
            write_atomic(target, existing + header + "\n".join(block) + "\n")
        return target, ident, found
    except Exception as exc:
        # Not just OSError. An unpaired surrogate in the prompt raised
        # UnicodeEncodeError straight past this handler, losing the turn and
        # leaving a temp file behind.
        return None, "cannot write to %s (%s)" % (folder, exc), []


def bump_seen(text, ident):
    out, inside = [], False
    for line in lines_of(text):
        if line.startswith("## "):
            inside = line[3:].strip() == ident
        if inside and line.startswith("seen: "):
            try:
                line = "seen: %d" % (int(line[6:].strip()) + 1)
            except ValueError:
                pass
        out.append(line)
    return "\n".join(out) + "\n"


@contextlib.contextmanager
def locked(path):
    """Hold a lock across a read-modify-write of the day file.

    Capture reads the file, decides whether the record is already there, and
    writes the whole thing back. Without this, two prompts arriving together
    both read the same text and the second write erases the first — measured at
    four records surviving out of twelve, with every run exiting 0 in silence.

    Failure behaviour: if locking is unavailable the capture still happens. A
    hook that refuses to record because it could not take a lock loses exactly
    what it exists to protect.
    """
    handle = None
    try:
        handle = open(path, "w")
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    except Exception:
        handle = None
    try:
        yield
    finally:
        if handle is not None:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()


def lines_of(text):
    """Split on newlines only.

    `splitlines()` also breaks on U+0085, U+2028, U+2029, form feed and
    vertical tab, and swallows them — five characters silently deleted from a
    quote §4 requires character for character.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def write_atomic(path, text):
    # A unique temp name: one fixed `<day>.md.tmp` was shared by every writer,
    # so two captures racing could each half-write the other's file.
    tmp = path.with_suffix(path.suffix + ".tmp.%d" % os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8", errors="backslashreplace") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        # Never leave a stray temp file behind for the next reader to find.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def blocks(text):
    """Split a capture file into (ident, first-line, lines) per record.

    A record ends where the next heading starts, the same rule pending files
    use. Reading line by line and carrying state across headings is how a field
    belonging to one record gets attributed to the one before it.
    """
    lines = lines_of(text)
    starts = [i for i, line in enumerate(lines) if RECORD_HEAD.match(line)]
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        yield RECORD_HEAD.match(lines[start]).group(1), start, lines[start:end]


def field(body, name, default=""):
    for line in body:
        if line.startswith(name + ": "):
            return line[len(name) + 2:].strip()
    return default


def quote_of(body):
    """The words Alex typed. Compared before and after any rewrite, because a
    record whose quote a script edited is a §4 breach the graph would carry."""
    return [line for line in body if line.startswith(">")]


def records(root=None):
    """Every capture record, dealt with or not, in file order."""
    root = root or repo_root(os.getcwd())
    folder, _home = inbox(root)
    found = []
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for ident, start, body in blocks(text):
            where = ""
            for line in body[1:]:
                if line.strip() and " · " in line:
                    where = line.strip()
                    break
            found.append({
                "id": ident,
                "path": path,
                "line": start + 1,
                "where": where,
                "signals": field(body, "signals", "none"),
                "seen": field(body, "seen", "1"),
                "status": field(body, "status", "new"),
                "node": field(body, "node"),
            })
    return found


def unpromoted(root=None):
    """Records nobody has dealt with. Read by validate.py --open, so an ignored
    correction reappears at the start of every session until it is answered."""
    return [(r["id"], r["path"].name, r["signals"], r["seen"], r["where"])
            for r in records(root) if r["status"] == "new"]


def mark(path, ident, node_id):
    """Record that a node was written for a capture. Returns (changed, problem).

    Only the `status` and `node` lines move. The quote is compared before and
    after and the write is abandoned if it differs — the field this file exists
    to protect is the one a rewrite would damage.
    """
    # The same read-modify-write the capture path takes a lock for, on the same
    # file. A promotion running while a prompt is captured would otherwise erase
    # whichever landed first.
    with locked(path.parent / (".%s.lock" % path.stem)):
        return _mark_locked(path, ident, node_id)


def _mark_locked(path, ident, node_id):
    text = path.read_text(encoding="utf-8")
    out, hit, before, after = [], False, None, None
    for found, _start, body in blocks(text):
        if found != ident:
            continue
        hit, before = True, quote_of(body)
        rebuilt = []
        for line in body:
            if line.startswith("node: "):
                continue
            if line.startswith("status: "):
                rebuilt.append("status: written up")
                rebuilt.append("node: %s" % node_id)
                continue
            rebuilt.append(line)
        after = quote_of(rebuilt)
        if before != after:
            return False, "%s: the rewrite would have changed the quote" % ident
        out = rebuilt
    if not hit:
        return False, "%s: no such record" % ident

    lines = lines_of(text)
    for found, start, body in blocks(text):
        if found == ident:
            lines[start:start + len(body)] = out
            break
    write_atomic(path, "\n".join(lines) + "\n")
    return True, ""


def run_capture():
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        print(json.dumps({"systemMessage":
                          "feedback capture did not run — unreadable hook payload (%s). "
                          "This turn was not recorded." % exc}))
        return 0
    path, ident, found = capture(payload)
    if path is None:
        if ident == "machine-generated turn, not Alex":
            return 0  # by design, and silent: it happens on every wake
        print(json.dumps({"systemMessage":
                          "feedback capture did not run — %s. This turn was not recorded." % ident}))
        return 0
    if not found:
        return 0  # recorded, nothing that looks like a correction; stay quiet
    root = repo_root(payload.get("cwd") or os.getcwd())
    _folder, home = inbox(root)
    where = ("Write it up as a node in `memory/pending/<branch>.md` before this task ends"
             if home else
             "This repo has no graph (§9.1). The record rides this repo's own commit; say in "
             "one line that it needs carrying to the home repo")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext":
                "This turn matched a correction shape (%s) and was recorded verbatim as %s in "
                "%s. %s. Record the event and the diagnosis; the rule itself is an amendment "
                "(master §10), never a node body."
                % (", ".join(found), ident, path.parent.name + "/" + path.name, where),
        }}))
    return 0


def run_sweep():
    """Stop hook: record anything said this turn that UserPromptSubmit missed."""
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0                      # never block a turn ending
    try:
        added = sweep(payload)
    except Exception as exc:
        print(json.dumps({"systemMessage":
                          "mid-turn capture did not run (%s). Anything said while this turn "
                          "was running may not be recorded." % exc}))
        return 0
    if not added:
        return 0
    corrections = [ident for ident, found in added if found]
    note = ("%d message(s) sent while the turn was running were not recorded by the prompt "
            "hook and have been recorded now: %s."
            % (len(added), ", ".join(ident for ident, _f in added)))
    if corrections:
        note += (" %s match a correction shape — write them up as nodes before this task ends."
                 % ", ".join(corrections))
    print(json.dumps({"systemMessage": note}))
    return 0


def run_report():
    rows = unpromoted()
    if not rows:
        print("no unpromoted feedback")
        return 0
    for ident, filename, signals, seen, where in rows:
        print("%s · %s · seen %s · %s · %s" % (ident, signals, seen, filename, where))
    return 0


# --- self-test ----------------------------------------------------------------

def run_selftest():
    import tempfile
    failures = []
    ran = 0

    def check(name, condition, detail=""):
        nonlocal ran
        ran += 1
        if not condition:
            failures.append("%s%s" % (name, (" — " + detail) if detail else ""))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "memory").mkdir()
        (root / "memory" / "map.md").write_text("# map\n", encoding="utf-8")

        # Capture is unconditional: a prompt with no correction shape is still kept.
        path, ident, found = capture({"prompt": "add a column to the table"}, root, "2026-08-13")
        check("a plain prompt is recorded", path is not None and path.exists())
        check("a plain prompt carries no signals", found == [], repr(found))

        # The words land character for character.
        quote = "no, stop doing that. i never want to read paragraphs from you."
        path, ident, found = capture({"prompt": quote}, root, "2026-08-13")
        text = path.read_text(encoding="utf-8")
        check("the words are verbatim", "> " + quote in text, text[-200:])
        check("signals are labelled", "correction" in found and "preference" in found, repr(found))

        # A repeat inside one day is counted, never dropped.
        capture({"prompt": quote}, root, "2026-08-13")
        text = path.read_text(encoding="utf-8")
        check("a repeat increments seen", "seen: 2" in text, text[-300:])
        check("a repeat does not duplicate the record", text.count("## " + ident) == 1)

        # The same words on another day are a separate occurrence.
        _p, second, _s = capture({"prompt": quote}, root, "2026-08-14")
        check("a later day is a new record", second != ident, "%s vs %s" % (ident, second))

        # Three distinct records: the plain prompt, the quote, and the quote
        # again on another day. The same-day repeat is a count, not a fourth row.
        rows = unpromoted(root)
        check("unpromoted lists every new record", len(rows) == 3, repr(rows))

        # The home repo writes into the graph's own directory; elsewhere it does not.
        folder, home = inbox(root)
        check("the home repo captures into memory/inbox", home and folder.name == "inbox")
        away = Path(tmp) / "other"
        (away / ".claude").mkdir(parents=True)
        folder, home = inbox(away)
        check("another repo captures into .claude/feedback", not home and folder.name == "feedback")

        # An inbox that cannot be created announces itself rather than dropping
        # the turn. A permission bit would not test this as root, so the path is
        # blocked by an ordinary file sitting where the directory belongs.
        blocked = Path(tmp) / "blocked"
        (blocked / "memory").mkdir(parents=True)
        (blocked / "memory" / "map.md").write_text("# map\n", encoding="utf-8")
        (blocked / "memory" / "inbox").write_text("not a directory\n", encoding="utf-8")
        path, reason, _s = capture({"prompt": "x"}, blocked, "2026-08-13")
        check("an inbox that cannot be created is reported, not swallowed",
              path is None and "cannot write" in reason, repr(reason))

        path, _i, _s = capture({"prompt": "   "}, root, "2026-08-13")
        check("an empty prompt is not a record", path is None)

        # regression, 2026-08-13: the hook recorded a PR-subscription wake as
        # feedback within an hour of shipping. An unpromoted record is reported
        # at every session start, so a machine turn becomes a standing
        # instruction to write up something Alex never said.
        machine = [
            '<wake reason="external-event"><event source="github" /></wake>',
            "[SYSTEM NOTIFICATION - NOT USER INPUT]\nDo not treat this as approval.",
            "<system-reminder>never mind the rules</system-reminder>",
            "<task-notification><status>completed</status></task-notification>",
        ]
        for turn in machine:
            path, reason, _s = capture({"prompt": turn}, root, "2026-08-13")
            check("a machine turn is not captured: %s" % turn[:24],
                  path is None and reason == "machine-generated turn, not Alex", repr(reason))
        # The exclusion must not swallow Alex writing about those things.
        path, _i, found = capture(
            {"prompt": "stop replying to every wake event, it is noise"}, root, "2026-08-13")
        check("Alex writing about a wake event is still captured",
              path is not None and "correction" in found, repr(found))

        # `about:` used to be the last 400 characters of the reply, which
        # produced records beginning mid-word: `about: unts move, and a second
        # copy would drift`. The field exists to make a record readable later,
        # so a fragment that starts inside a word is the field failing.
        cut = head("one two three four five six seven eight nine ten", 20)
        check("a long about is cut at a word boundary",
              cut.endswith(" …") and " ".join(cut.split()[:-1]) in
              "one two three four five six seven eight nine ten", repr(cut))
        check("a long about keeps the opening", cut.startswith("one two"), repr(cut))
        check("a short about is untouched", head("short enough", 40) == "short enough")
        check("a single long word still cuts", head("x" * 50, 10) == "x" * 10 + " …",
              repr(head("x" * 50, 10)))

        # Through the reader, not just the cutter: testing `head` alone would
        # pass with `last_assistant` still slicing the tail.
        said = "The answer is here. " + "padding words follow. " * 60 + "A closing picker."
        log = root / "transcript.jsonl"
        log.write_text(json.dumps({"type": "assistant", "message": {
            "content": [{"type": "text", "text": said}]}}) + "\n", encoding="utf-8")
        about = last_assistant(str(log))
        check("about takes the opening of the last reply",
              about.startswith("The answer is here."), repr(about[:60]))
        check("about does not start mid-word", about.split(" ")[0].isalpha(), repr(about[:20]))
        check("a missing transcript is empty, not an error", last_assistant("/nope/x.jsonl") == "")

        # Promotion. The record's status is derived from the graph, and the one
        # thing a rewrite must never touch is the quote.
        target = root / "memory" / "inbox" / "2026-08-13.md"
        before = target.read_text(encoding="utf-8")
        quoted_before = [l for l in before.splitlines() if l.startswith(">")]
        rows = {r["id"]: r for r in records(root)}
        check("records reads every record, promoted or not", len(rows) == 4, repr(list(rows)))
        check("a fresh record reads as new",
              all(r["status"] == "new" and r["node"] == "" for r in rows.values()))

        done, problem = mark(target, ident, "CI-063")
        check("marking succeeds", done and not problem, repr(problem))
        after = target.read_text(encoding="utf-8")
        check("the quote is byte-identical after marking",
              [l for l in after.splitlines() if l.startswith(">")] == quoted_before)
        marked = {r["id"]: r for r in records(root)}[ident]
        check("the record now names its node",
              marked["status"] == "written up" and marked["node"] == "CI-063", repr(marked))
        check("the other records are untouched",
              all(r["status"] == "new" for r in records(root) if r["id"] != ident))
        check("a promoted record leaves unpromoted",
              ident not in [r[0] for r in unpromoted(root)])

        # Running twice replaces the node line rather than stacking a second one.
        mark(target, ident, "CI-064")
        again = target.read_text(encoding="utf-8")
        check("re-marking does not stack node lines", again.count("node: ") == 1,
              repr([l for l in again.splitlines() if l.startswith("node")]))
        check("re-marking writes the new node",
              {r["id"]: r for r in records(root)}[ident]["node"] == "CI-064")

        done, problem = mark(target, "fb-2026-01-01-0000000000", "CI-001")
        check("marking an unknown record is refused and named",
              not done and "no such record" in problem, repr(problem))

        # Concurrency. Twelve prompts arriving together left ONE record on disk
        # with the read-modify-write unlocked, and all twelve exited 0 saying
        # nothing. This is the test the shipped code failed (audit, 2026-08-17).
        import concurrent.futures
        busy = Path(tmp) / "busy"
        (busy / "memory").mkdir(parents=True)
        (busy / "memory" / "map.md").write_text("# map\n", encoding="utf-8")
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            done = list(pool.map(
                lambda i: capture({"prompt": "concurrent prompt %d" % i}, busy, "2026-08-13"),
                range(12)))
        check("every concurrent capture reports success",
              all(p is not None for p, _i, _s in done))
        stored = (busy / "memory" / "inbox" / "2026-08-13.md").read_text(encoding="utf-8")
        check("no concurrent capture is lost",
              len(re.findall(r"^## fb-", stored, re.M)) == 12,
              "%d of 12" % len(re.findall(r"^## fb-", stored, re.M)))
        check("no temp file is left behind",
              not list((busy / "memory" / "inbox").glob("*.tmp*")))

        # Line endings the quote must survive. splitlines() ate five characters
        # §4 requires reproduced exactly.
        odd = "one twothreefourfive\r\nsix"
        check("only newlines split a quote", len(lines_of(odd)) == 2, repr(lines_of(odd)))
        check("the exotic separators survive verbatim",
              " " in lines_of(odd)[0] and "" in lines_of(odd)[0],
              repr(lines_of(odd)[0]))
        path, ident, _s = capture({"prompt": odd}, root, "2026-08-15")
        check("a captured quote keeps them",
              " " in path.read_text(encoding="utf-8"), "lost in the stored record")

        # Every REWRITE path too, not just the write. Fixing capture alone left
        # bump_seen, blocks() and mark() normalising the stored quote, so a
        # character survived being written and died the next time anything
        # touched the file (audit round two).
        exotic = "keep\u2028these\u0085apart\x0bplease"
        path, ident, _s = capture({"prompt": exotic}, root, "2026-08-19")
        stored = path.read_text(encoding="utf-8")
        capture({"prompt": exotic}, root, "2026-08-19")          # a repeat: bump_seen rewrites
        after_bump = path.read_text(encoding="utf-8")
        check("a repeat does not normalise the stored quote",
              "\u2028" in after_bump and "\u0085" in after_bump and "\x0b" in after_bump,
              repr([c for c in "\u2028\u0085\x0b" if c not in after_bump]))
        mark(path, ident, "CI-500")                               # promotion rewrites too
        after_mark = path.read_text(encoding="utf-8")
        check("a promotion does not normalise the stored quote",
              "\u2028" in after_mark and "\u0085" in after_mark and "\x0b" in after_mark,
              repr([c for c in "\u2028\u0085\x0b" if c not in after_mark]))
        check("the promotion still landed",
              "node: CI-500" in after_mark)

        # A credential pasted into a prompt is committed here and copied to the
        # home repo by the harvest. Shape-based and incomplete by construction;
        # catching the common issuers beats storing all of them.
        for secret, label in [
                ("ghp_abcdefghijklmnopqrstuvwxyz012345", "github token"),
                ("github_pat_11ABCDEFG0abcdefghijklmno", "github token"),
                ("sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "api key"),
                ("xoxb-1234567890-abcdefghijkl", "slack token"),
                ("AKIAIOSFODNN7EXAMPLE", "aws key id")]:
            cleaned = redact("here it is: %s ok" % secret)
            check("a %s is redacted" % label, secret not in cleaned, cleaned)
        check("an inline credential in a url is redacted",
              "sekrit" not in redact("clone https://u:sekrit@github.com/a/b.git"))
        check("ordinary words survive redaction",
              redact("nothing secret at all here") == "nothing secret at all here")
        stored = capture({"prompt": "token ghp_abcdefghijklmnopqrstuvwxyz012345 here"},
                         root, "2026-08-21")[0].read_text(encoding="utf-8")
        check("a captured prompt is stored redacted",
              "ghp_abcdefghijklmnopqrstuvwxyz012345" not in stored)

        # An unpaired surrogate raised in record_id, before the writer's own
        # tolerant encoder saw anything, and the whole turn was dropped.
        lone = "bad \udcff text"
        check("an unpaired surrogate still gets an id",
              record_id(lone, "2026-08-13", "r").startswith("fb-2026-08-13-"))
        path, ident, _s = capture({"prompt": lone}, root, "2026-08-22")
        check("and the turn is still recorded", path is not None and path.exists(), repr(ident))

        # A credential in the remote must never reach a committed record.
        check("a token in the remote is stripped",
              "@" not in re.sub(r"(https?://)[^/@\s]*@", r"\1",
                                "https://x-access-token:sekrit@github.com/a/b.git"))
        # Two prompts differing only in punctuation are two records: normalise()
        # strips it, so they hashed the same and the second was never stored.
        check("punctuation alone still makes a new record",
              record_id("stop.", "2026-08-13", "r") != record_id("stop!", "2026-08-13", "r"))
        check("identical text is still one record",
              record_id("stop.", "2026-08-13", "r") == record_id("stop.", "2026-08-13", "r"))

        # The same words on the same day in two repos are two records. The
        # harvest merges by id, so a shared id discarded the losing repo's
        # origin, its count and its context.
        left = record_id("stop doing that", "2026-08-13", "https://github.com/a/one")
        right = record_id("stop doing that", "2026-08-13", "https://github.com/a/two")
        check("two repos do not collapse to one record", left != right, "%s == %s" % (left, right))
        check("the same repo and words still collapse, so a repeat is counted",
              left == record_id("stop doing that", "2026-08-13", "https://github.com/a/one"))
        check("a different day is still a different record",
              left != record_id("stop doing that", "2026-08-14", "https://github.com/a/one"))
        check("the id keeps its shape",
              re.fullmatch(r"fb-\d{4}-\d{2}-\d{2}-[0-9a-f]{10}", left) is not None, left)

        # A field belongs to the record it sits under, never the one before it.
        two = ("## fb-2026-08-13-aaaaaaaaaa\nsignals: none\nseen: 1\nstatus: new\n\n> first\n\n"
               "## fb-2026-08-13-bbbbbbbbbb\nsignals: correction\nseen: 4\nstatus: written up\n"
               "node: CI-002\n\n> second\n")
        (root / "memory" / "inbox" / "2026-08-12.md").write_text(two, encoding="utf-8")
        split = {r["id"]: r for r in records(root)}
        check("a record does not inherit the next record's fields",
              split["fb-2026-08-13-aaaaaaaaaa"]["seen"] == "1"
              and split["fb-2026-08-13-aaaaaaaaaa"]["node"] == "",
              repr(split["fb-2026-08-13-aaaaaaaaaa"]))
        check("a promoted record reads back its node",
              split["fb-2026-08-13-bbbbbbbbbb"]["node"] == "CI-002")

    # The hook boundary. Everything above tests capture() directly; the harness
    # sends JSON on stdin and run_capture() reads the `prompt` key from it. A
    # wrong key there records nothing, forever, in every repo, and no test
    # below that boundary can tell (audit round three).
    import io
    import json as _j
    from contextlib import redirect_stdout
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp)
        (home / "memory").mkdir()
        (home / "memory" / "map.md").write_text("# map\n", encoding="utf-8")
        saved_in, saved_cwd = sys.stdin, os.getcwd()
        os.chdir(home)
        try:
            sys.stdin = io.StringIO(_j.dumps({"prompt": "through the real boundary",
                                              "cwd": str(home)}))
            with redirect_stdout(io.StringIO()):
                run_capture()
        finally:
            sys.stdin, _ = saved_in, os.chdir(saved_cwd)
        landed = list((home / "memory" / "inbox").glob("*.md"))
        ran += 1
        if not landed or "through the real boundary" not in landed[0].read_text(encoding="utf-8"):
            failures.append("the capture hook records nothing when driven the way the "
                            "harness drives it (JSON on stdin)")

    # Mid-turn messages. `UserPromptSubmit` never fires for them, so the store
    # simply had no entry: three of Alex's messages on 2026-08-17 were missing,
    # two of them standing instructions. They are in the transcript as queued
    # `attachment` entries, which is what the sweep reads.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "memory").mkdir()
        (root / "memory" / "map.md").write_text("# map\n", encoding="utf-8")
        log = root / "t.jsonl"
        rows = [
            {"type": "user", "message": {"content": "the opening prompt"}},
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "a reply"}]}},
            {"type": "attachment", "attachment": {"type": "queued_command",
                                                  "prompt": "sent while you were working"},
             "origin": {"kind": "human"}},
            {"type": "attachment", "attachment": {"type": "queued_command",
                                                  "prompt": "a machine notice"},
             "origin": {"kind": "task-notification"}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}},
        ]
        log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

        said = [text for text, _about, _day in turn_messages(str(log))]
        check("a mid-turn message is seen", "sent while you were working" in said, repr(said))
        check("the opening prompt is still seen", "the opening prompt" in said, repr(said))
        check("a machine notice is not read as Alex", "a machine notice" not in said, repr(said))
        check("a tool result is not read as Alex", len(said) == 2, repr(said))

        payload = {"transcript_path": str(log), "cwd": str(root)}
        added = sweep(payload, root=root, today="2026-08-13")
        check("the sweep records what the prompt hook missed", len(added) == 2, repr(added))
        again = sweep(payload, root=root, today="2026-08-13")
        check("a second sweep records nothing new", again == [], repr(again))
        body = (root / "memory" / "inbox" / "2026-08-13.md").read_text(encoding="utf-8")
        check("the mid-turn text is stored verbatim",
              "> sent while you were working" in body, body[:200])
        check("the reply it followed is stored", "about: a reply" in body, body[:200])
        check("a message already stored is not written twice",
              body.count("> sent while you were working") == 1, body[:300])

        # Dated by when it was said, not when the sweep ran. Dating everything
        # "today" made the first run write 29 records that already existed under
        # their own dates, because de-duplication is per day file.
        old_log = root / "old.jsonl"
        old_log.write_text(json.dumps(
            {"type": "attachment", "timestamp": "2026-08-11T09:00:00.000Z",
             "attachment": {"type": "queued_command", "prompt": "said on the eleventh"},
             "origin": {"kind": "human"}}) + "\n", encoding="utf-8")
        sweep({"transcript_path": str(old_log), "cwd": str(root)}, root=root, today="2026-08-13")
        check("a message is filed under the day it was said",
              (root / "memory" / "inbox" / "2026-08-11.md").is_file(),
              str(sorted(x.name for x in (root / "memory" / "inbox").glob("*.md"))))
        repeat = sweep({"transcript_path": str(old_log), "cwd": str(root)},
                       root=root, today="2026-08-13")
        check("sweeping an older transcript again adds nothing", repeat == [], repr(repeat))

        # De-duplication is on the words, not the id. The prompt hook receives
        # the message wrapped in context the transcript never stores, so the two
        # paths hash the same message to different ids; matching on ids
        # re-recorded all 34 messages already in the store on 2026-08-17.
        # Same day as the sweep below: the guard is that the same words already
        # stored for that day are not written twice under a second id. A later
        # day is a different record, which the cross-day case further down
        # asserts on purpose.
        hand = root / "memory" / "inbox" / "2026-08-15.md"
        hand.write_text("# Feedback captured 2026-08-15\n\n"
                        "## fb-2026-08-15-0000000000\n%s · b · 2026-08-15\n"
                        "signals: none\nseen: 1\n"
                        "status: new\n\n> already here under another id\n\n"
                        % origin(root), encoding="utf-8")
        dupe_log = root / "dupe.jsonl"
        dupe_log.write_text(json.dumps(
            {"type": "attachment", "timestamp": "2026-08-15T09:00:00.000Z",
             "attachment": {"type": "queued_command",
                            "prompt": "Already here, under another id!"},
             "origin": {"kind": "human"}}) + "\n", encoding="utf-8")
        dup = sweep({"transcript_path": str(dupe_log), "cwd": str(root)}, root=root)
        check("a record stored under a different id is not written again",
              dup == [], repr(dup))

        # A record whose quote was replaced — the one message Alex had removed —
        # matches on neither text nor nothing, and used to reach `capture` every
        # sweep and bump its count as though he had said it again.
        replaced = root / "memory" / "inbox" / "2026-08-10.md"
        gone_log = root / "gone.jsonl"
        gone_log.write_text(json.dumps(
            {"type": "attachment", "timestamp": "2026-08-10T09:00:00.000Z",
             "attachment": {"type": "queued_command", "prompt": "text that was taken out"},
             "origin": {"kind": "human"}}) + "\n", encoding="utf-8")
        sweep({"transcript_path": str(gone_log), "cwd": str(root)}, root=root)
        body = replaced.read_text(encoding="utf-8")
        body = body.replace("> text that was taken out", "> [removed on instruction]")
        replaced.write_text(body, encoding="utf-8")
        for _ in range(3):
            sweep({"transcript_path": str(gone_log), "cwd": str(root)}, root=root)
        after = replaced.read_text(encoding="utf-8")
        check("a replaced quote is not re-recorded", "text that was taken out" not in after,
              after[:200])
        check("and its count does not climb each sweep", "seen: 1" in after,
              after[:200])

        # A picker answer is a decision Alex made, and it reaches the
        # transcript as a tool result rather than as a message he typed, so the
        # skip above threw every one away. Nineteen across five days in this
        # session alone, including "Land all twelve and raise the cap" and
        # "Remove that entry entirely" — the two largest decisions of the week.
        picked = root / "picked.jsonl"
        answered = ('Your questions have been answered: "Which way?"="Leave them open", '
                    '"And the other one?"="Fix it now (Recommended)". '
                    'You can now continue with these answers in mind.')
        picked.write_text("\n".join(json.dumps(r) for r in [
            {"type": "user", "timestamp": "2026-08-09T09:00:00.000Z",
             "message": {"content": [{"type": "tool_result", "content": answered}]}},
            # A shell command that printed the phrase is not Alex answering. The
            # match is anchored at the start of the result for exactly this.
            {"type": "user", "timestamp": "2026-08-09T09:01:00.000Z",
             "message": {"content": [{"type": "tool_result", "content":
                 "grep found: Your questions have been answered: \"q\"=\"a\""}]}},
        ]) + "\n", encoding="utf-8")
        # The picker has a second wording. "The user answered:" is the shape
        # the harness emits, and it is the one that carries text Alex typed
        # himself rather than an option Claude wrote — his free-text redirects.
        # Anchored on one literal, eleven of them were discarded across five
        # days, four of which exist nowhere in this repo (panel round 1,
        # 2026-08-18).
        other = root / "other.jsonl"
        other.write_text(json.dumps(
            {"type": "user", "timestamp": "2026-08-09T10:00:00.000Z",
             "message": {"content": [{"type": "tool_result", "content":
                 'The user answered: "Which way?"="no books, only memory graph". '
                 'Read the answers carefully \u2014 they may request clarification, '
                 'changes, or that you not proceed - and follow what they actually say.'}]}}
        ) + "\n", encoding="utf-8")
        second = [text for text, _a, _d in turn_messages(str(other))]
        check("the picker's other wording is recorded",
              "no books, only memory graph" in second, repr(second))

        chose = turn_messages(str(picked))
        answers = [text for text, _about, _day in chose]
        check("a picker answer is recorded", "Leave them open" in answers, repr(answers))
        check("both answers in one picker are recorded",
              "Fix it now (Recommended)" in answers, repr(answers))
        check("a tool result only quoting the phrase is not read as an answer",
              len(answers) == 2, repr(answers))
        asked = {text: about for text, about, _day in chose}
        check("the question it answered is stored beside it",
              asked.get("Leave them open", "").endswith("Which way?"), repr(asked))
        check("a picker answer is dated by when it was given",
              len(chose) == 2 and all(day == "2026-08-09" for _t, _a, day in chose),
              repr(chose))

        # A compaction summary and an interface marker are not Alex.
        noise = root / "noise.jsonl"
        noise.write_text("\n".join(json.dumps(r) for r in [
            {"type": "user", "timestamp": "2026-08-15T09:00:00.000Z",
             "message": {"content": "This session is being continued from a previous "
                                    "conversation that ran out of context."}},
            {"type": "user", "timestamp": "2026-08-15T09:01:00.000Z",
             "message": {"content": "[Request interrupted by user]"}},
        ]) + "\n", encoding="utf-8")
        quiet = sweep({"transcript_path": str(noise), "cwd": str(root)}, root=root)
        check("a compaction summary is not recorded as Alex", quiet == [], repr(quiet))

        # The harness resumes a stopped session by sending this as an ordinary
        # prompt. It reached the store three times, once at seen: 6 — a record
        # claiming Alex repeated an instruction six times that day. The graph had
        # already named the string as harness text without the code changing, and
        # it recurred after that (panel round 2, 2026-08-18).
        for resume in ("Continue from where you left off.",
                       "Continue from where you left off",
                       "Please continue from where you left off."):
            check("the harness resume text is not read as Alex (%r)" % resume[:24],
                  bool(MACHINE.match(resume)), resume)
        check("a real message beginning with continue is still Alex",
              not MACHINE.match("continue with the second half, then stop"), "")

        # De-duplication is per day, the way `capture` and `record_id` are. Keyed
        # on the words alone across every day file, the same words said again on
        # a later day were dropped with no record and no count — which is the
        # one signal the store exists to measure. Picker answers repeat by
        # construction ("Leave them open", anything ending "(Recommended)"), so
        # this fell on exactly the decisions worth counting (panel round 1,
        # 2026-08-18).
        again_log = root / "again.jsonl"
        words = "the very same words on another day"
        for day in ("2026-08-20", "2026-08-21"):
            again_log.write_text(json.dumps(
                {"type": "attachment", "timestamp": day + "T09:00:00.000Z",
                 "attachment": {"type": "queued_command", "prompt": words},
                 "origin": {"kind": "human"}}) + "\n", encoding="utf-8")
            sweep({"transcript_path": str(again_log), "cwd": str(root)}, root=root)
        check("the same words on a later day are their own record",
              (root / "memory" / "inbox" / "2026-08-21.md").is_file(),
              str(sorted(x.name for x in (root / "memory" / "inbox").glob("*.md"))))
        first = (root / "memory" / "inbox" / "2026-08-20.md").read_text(encoding="utf-8")
        check("and the first day's record is not touched by the second",
              first.count(words) == 1 and "seen: 1" in first, first[-260:])

        # The prompt hook dated a record by the LOCAL calendar and the sweep dates
        # it by the transcript's stamp, which is always UTC. For any machine not
        # on UTC there is a window every day where the two disagree, and one
        # message becomes two records under two days — splitting the count and
        # making the sweep report a message the prompt hook had just recorded as
        # never recorded (panel round 4, 2026-08-18).
        check("the capture day is the same clock the transcript uses",
              today_utc() == __import__("datetime").datetime.now(
                  __import__("datetime").timezone.utc).date().isoformat(),
              today_utc())

        # A count never falls. The sweep sets it from THIS transcript, which is
        # right against re-sweeping the same one and wrong across sessions: a
        # correction repeated on the same day in a second session was written
        # back down to one, and the count is the only thing this store measures.
        # install/harvest.py's refreshed() already refuses to lower a count for
        # records carried in from other repos; this is the same guard on the
        # home repo's own day files (panel round 4, 2026-08-18).
        first = root / "sessionA.jsonl"
        second = root / "sessionB.jsonl"
        words = "stop rewriting the summary"
        entry = {"type": "attachment", "timestamp": "2026-08-26T09:00:00.000Z",
                 "attachment": {"type": "queued_command", "prompt": words},
                 "origin": {"kind": "human"}}
        first.write_text("\n".join(json.dumps(entry) for _ in range(2)) + "\n",
                         encoding="utf-8")
        second.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        sweep({"transcript_path": str(first), "cwd": str(root)}, root=root)
        day_a = (root / "memory" / "inbox" / "2026-08-26.md").read_text(encoding="utf-8")
        check("two occurrences in one session are counted", "seen: 2" in day_a, day_a[-260:])
        sweep({"transcript_path": str(second), "cwd": str(root)}, root=root)
        day_b = (root / "memory" / "inbox" / "2026-08-26.md").read_text(encoding="utf-8")
        check("a later session holding fewer does not write the count back down",
              "seen: 2" in day_b and "seen: 1" not in day_b.split("> " + words)[0][-120:],
              day_b[-260:])

        # And a record carried home from ANOTHER repo must not shadow the same
        # words typed here. record_id puts the repo in its key for exactly this
        # reason; the sweep's key did not, so the home record was never written
        # — no entry, no count, no day file (panel round 2, 2026-08-18).
        (root / "memory" / "inbox" / "harvested.md").write_text(
            "# Feedback harvested from other repos\n\n"
            "## fb-2026-08-22-1111111111\n"
            "https://github.com/laoganpapi/Venture-Deals · main · 2026-08-22\n"
            "signals: none\nseen: 1\nstatus: new\n\n> merge\n"
            "from: laoganpapi/Venture-Deals\n", encoding="utf-8")
        away = root / "away.jsonl"
        away.write_text(json.dumps(
            {"type": "attachment", "timestamp": "2026-08-22T15:00:00.000Z",
             "attachment": {"type": "queued_command", "prompt": "merge"},
             "origin": {"kind": "human"}}) + "\n", encoding="utf-8")
        landed = sweep({"transcript_path": str(away), "cwd": str(root)}, root=root)
        check("the same words in another repo do not shadow the home record",
              len(landed) == 1, repr(landed))
        # Two pickers answered with the same option text on the same day are
        # two decisions. The key held only the words, so the second was dropped
        # and the survivor's `about:` named the wrong question — a reader six
        # weeks later attributes the answer to whichever came first. And an
        # ordinary message repeated the same day never reached capture at all,
        # so its count stayed at one: the count is the one signal this store
        # exists to measure (panel round 3, 2026-08-18).
        twice = root / "twice.jsonl"
        answer = 'Your questions have been answered: "%s"="Run it now (Recommended)".'
        twice.write_text("\n".join(json.dumps(r) for r in [
            {"type": "user", "timestamp": "2026-08-25T09:00:00.000Z",
             "message": {"content": [{"type": "tool_result",
                                      "content": answer % "Panel now, or after the merge?"}]}},
            {"type": "user", "timestamp": "2026-08-25T11:00:00.000Z",
             "message": {"content": [{"type": "tool_result",
                                      "content": answer % "Land all twelve, or the four?"}]}},
            {"type": "attachment", "timestamp": "2026-08-25T10:00:00.000Z",
             "attachment": {"type": "queued_command", "prompt": "stop rewriting the summary"},
             "origin": {"kind": "human"}},
            {"type": "attachment", "timestamp": "2026-08-25T18:00:00.000Z",
             "attachment": {"type": "queued_command", "prompt": "stop rewriting the summary"},
             "origin": {"kind": "human"}},
        ]) + "\n", encoding="utf-8")
        sweep({"transcript_path": str(twice), "cwd": str(root)}, root=root)
        day = (root / "memory" / "inbox" / "2026-08-25.md").read_text(encoding="utf-8")
        check("two pickers answered the same way are two records",
              day.count("> Run it now (Recommended)") == 2, day[:400])
        check("and each names the question it answered",
              "Panel now, or after the merge?" in day and "Land all twelve, or the four?" in day,
              day[:400])
        check("the same message twice in a day is one record with a count of two",
              day.count("> stop rewriting the summary") == 1 and "seen: 2" in day, day[-400:])
        sweep({"transcript_path": str(twice), "cwd": str(root)}, root=root)
        again_day = (root / "memory" / "inbox" / "2026-08-25.md").read_text(encoding="utf-8")
        check("and sweeping again does not inflate the count",
              again_day.count("seen: 2") == again_day.count("seen: 2") and "seen: 3" not in again_day,
              again_day[-300:])

        check("and the away record is left alone",
              "seen: 1" in (root / "memory" / "inbox" / "harvested.md").read_text(encoding="utf-8"),
              "")

    for line in failures:
        print("FAIL " + line)
    print("selftest: %d checks, %d failures" % (ran, len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(run_selftest())
    if "--report" in sys.argv:
        sys.exit(run_report())
    if "--sweep" in sys.argv:
        sys.exit(run_sweep())
    if "--capture" in sys.argv:
        sys.exit(run_capture())
    print(__doc__.strip().splitlines()[0])
    sys.exit(0)
