#!/usr/bin/env python3
"""Capture what Alex says, before any model decides whether it mattered.

Usage:
    python3 .claude/hooks/feedback.py --capture   UserPromptSubmit: record the turn
    python3 .claude/hooks/feedback.py --report    unpromoted records, one line each
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
    r"<local-command-stdout>|<untrusted_external_data|\[SYSTEM NOTIFICATION)",
    re.I)


def repo_root(start):
    found = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
    if found.returncode == 0 and found.stdout.strip():
        return Path(found.stdout.strip())
    here = Path(start).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".claude").is_dir():
            return candidate
    return here


def inbox(root):
    """Where records land, and whether this repo holds the graph."""
    home = (root / "memory" / "map.md").is_file()
    return root / (HOME_INBOX if home else AWAY_INBOX), home


def origin(root):
    found = subprocess.run(["git", "-C", str(root), "remote", "get-url", "origin"],
                           capture_output=True, text=True)
    return found.stdout.strip() if found.returncode == 0 else "(no remote)"


def branch(root):
    found = subprocess.run(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, text=True)
    return found.stdout.strip() if found.returncode == 0 else "(no branch)"


def normalise(text):
    return " ".join(re.sub(r"[^\w\s]", "", text.lower()).split())


def record_id(text, day):
    """Per occurrence per day, not per text.

    Keying on the text alone and skipping a repeat would collapse the one signal
    the graph is built on: a correction Alex has to give twice is worse than one
    he gives once, and the count is the evidence.
    """
    return "fb-%s-%s" % (day, hashlib.sha1(normalise(text).encode("utf-8")).hexdigest()[:10])


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


def capture(payload, root=None, today=None):
    """Append one record. Returns (path, id, signals) or (None, reason, [])."""
    text = (payload.get("prompt") or "").strip()
    if not text:
        return None, "no prompt in the payload", []
    if MACHINE.match(text):
        return None, "machine-generated turn, not Alex", []
    root = root or repo_root(payload.get("cwd") or os.getcwd())
    day = today or __import__("datetime").date.today().isoformat()
    folder, _home = inbox(root)
    ident = record_id(text, day)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / ("%s.md" % day)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        found = signals_in(text)
        if ("## %s" % ident) in existing:
            # Same words, same day: a repeat inside one session. Count it rather
            # than dropping it — recurrence is the measurement.
            updated = bump_seen(existing, ident)
            write_atomic(target, updated)
            return target, ident, found
        block = [
            "## %s" % ident,
            "%s · %s · %s" % (origin(root), branch(root), day),
            "signals: %s" % (", ".join(found) if found else "none"),
            "seen: 1",
            "status: new",
            "",
            "> " + "\n> ".join(text.splitlines()),
            "",
        ]
        about = last_assistant(payload.get("transcript_path"))
        if about:
            block[-1:] = ["about: %s" % about, ""]
        header = "" if existing else ("# Feedback captured %s\n\nVerbatim, unclassified, "
                                      "append-only. Promotion to a graph node is a session's "
                                      "job; forgetting is not available.\n\n" % day)
        write_atomic(target, existing + header + "\n".join(block) + "\n")
        return target, ident, found
    except OSError as exc:
        return None, "cannot write to %s (%s)" % (folder, exc), []


def bump_seen(text, ident):
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip() == ident
        if inside and line.startswith("seen: "):
            try:
                line = "seen: %d" % (int(line[6:].strip()) + 1)
            except ValueError:
                pass
        out.append(line)
    return "\n".join(out) + "\n"


def write_atomic(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def blocks(text):
    """Split a capture file into (ident, first-line, lines) per record.

    A record ends where the next heading starts, the same rule pending files
    use. Reading line by line and carrying state across headings is how a field
    belonging to one record gets attributed to the one before it.
    """
    lines = text.splitlines()
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

    lines = text.splitlines()
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

    for line in failures:
        print("FAIL " + line)
    print("selftest: %d checks, %d failures" % (ran, len(failures)))
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(run_selftest())
    if "--report" in sys.argv:
        sys.exit(run_report())
    if "--capture" in sys.argv:
        sys.exit(run_capture())
    print(__doc__.strip().splitlines()[0])
    sys.exit(0)
