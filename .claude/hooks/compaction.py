#!/usr/bin/env python3
"""Notice that the conversation was compacted, and say what that cost.

Usage:
    python3 .claude/hooks/compaction.py --check     UserPromptSubmit mode
    python3 .claude/hooks/compaction.py --selftest  run the built-in tests

Compaction replaces the earlier conversation with a summary to free space. It
happens without announcement, and the session carries on as though nothing
moved. What it loses is uneven, and that is the problem:

    `.claude/universal.md` is re-imported, so the compressed rules survive.
    `memory/rules.md` was an ordinary file read, so it does not.

The session is left holding a summary of the rules and missing the detail it is
required to consult whenever a rule is unclear (master §5.5), with nothing
telling it so. A pointed lookup silently becomes recall, which is the same
silent-approval class the rest of this repo exists to close.

Detection reads the transcript rather than relying on a compaction event
reaching the model. The boundary is written as a `system` entry with
`subtype: compact_boundary`, carrying `compactMetadata` — verified against a
real boundary in this repo's own session log, 2026-08-12T08:31:14Z, trigger
`auto`, 824,052 tokens before.

State lives outside the repository, so a detector never dirties the git tree
and is never scanned by the pre-delivery hook.

Failure behaviour: an unreadable transcript, an unreadable payload, and an
unwritable state file are each reported and then allowed through. A missed
notice is a worse outcome than a duplicate one, so on any doubt it speaks.
"""

import json
import pathlib
import os
import sys
from pathlib import Path

# The whole transcript is scanned, not a tail. A tail was tried first and was
# wrong: a compaction followed by heavy tool output scrolls the boundary out of
# any fixed window, and the boundary in this repo's own session sits 9 MB from
# the end. Only lines containing the marker are parsed as JSON, so the cost is a
# substring test per line.
MARKER = '"compact_boundary"'


def state_path(session_id: str) -> Path:
    root = Path(os.environ.get("TMPDIR", "/tmp"))
    safe = "".join(c for c in (session_id or "unknown") if c.isalnum() or c in "-_")
    return root / f"claude-compaction-{safe or 'unknown'}.json"


def newest_boundary(transcript: str):
    """The most recent compaction boundary in the transcript tail.

    Returns (uuid, metadata, timestamp) or (None, None, None). A malformed
    line is skipped rather than aborting the scan: the format is internal and
    undocumented, and one bad entry must not hide a real boundary.
    """
    found = (None, None, None)
    try:
        with Path(transcript).open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if MARKER not in line:
                    continue
                try:
                    entry = json.loads(line.strip())
                except ValueError:
                    continue
                if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
                    found = (entry.get("uuid"),
                             entry.get("compactMetadata") or {},
                             entry.get("timestamp"))
    except OSError as exc:
        return None, None, f"transcript unreadable: {exc}"
    return found


def notice(metadata: dict, timestamp) -> str:
    trigger = metadata.get("trigger", "unknown")
    pre = metadata.get("preTokens")
    size = f", {pre:,} tokens before it" if isinstance(pre, int) else ""
    return (
        f"The conversation was compacted at {timestamp} (trigger: {trigger}{size}). "
        f"Everything before that point is now a summary written by another pass, not the "
        f"original text. What that means for this turn, in order of what it costs:\n"
        f"\n"
        f"1. `memory/rules.md` is a path again, not content. `.claude/universal.md` "
        f"is re-imported and survived, so the compressed rules are present and the detail "
        f"behind them is not. Re-read the master before citing any § or resolving any rule "
        f"ambiguity (§5.5) — a lookup answered from the summary is recall wearing a citation.\n"
        f"2. Every material fact restated from here on is memory until checked. Read "
        f"`memory/map.md` and the domain file before stating one (§3.5).\n"
        f"3. Every binding term is unverified until its source is read again. The summary is "
        f"never a substitute for the document (§4.3).\n"
        f"4. Any file read before the boundary is a summary of a file. Re-read it before "
        f"relying on its contents.\n"
        f"\n"
        f"Context pressure is not a degradation signal and is not a reason to stop "
        f"mid-deliverable (§5.3). Bring the graph current, then carry on."
    )


def run_check() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        print(json.dumps({"systemMessage":
                          "compaction check did not run: unreadable hook payload"}))
        return 0

    transcript = payload.get("transcript_path")
    if not transcript:
        print(json.dumps({"systemMessage":
                          "compaction check did not run: no transcript_path in the payload"}))
        return 0

    uuid, metadata, timestamp = newest_boundary(transcript)
    if uuid is None:
        if isinstance(timestamp, str) and timestamp.startswith("transcript unreadable"):
            print(json.dumps({"systemMessage": f"compaction check did not run: {timestamp}"}))
        return 0  # no compaction has happened in this session

    path = state_path(payload.get("session_id", ""))
    seen = None
    try:
        seen = json.loads(path.read_text(encoding="utf-8")).get("uuid")
    except (OSError, ValueError):
        seen = None  # first prompt, or state lost with the container

    if seen == uuid:
        return 0  # already announced

    reply = {"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": notice(metadata, timestamp),
    }}
    try:
        path.write_text(json.dumps({"uuid": uuid}), encoding="utf-8")
    except OSError:
        # Losing the marker means the notice repeats next turn. Repeating is the
        # safe direction, so this is reported and not treated as a failure.
        #
        # In ONE document. Printing a second alongside the notice meant the
        # hook emitted two JSON documents on stdout, where a single one is
        # expected — most likely discarding the notice in exactly the branch
        # this code says it handles (audit round three).
        reply["systemMessage"] = ("compaction notice sent, but its marker could not be "
                                  "saved; it may repeat next turn")
    print(json.dumps(reply))
    return 0


# --- self-test ----------------------------------------------------------------

def run_selftest() -> int:
    import tempfile
    failures = []

    boundary = {
        "type": "system", "subtype": "compact_boundary", "uuid": "abc-123",
        "timestamp": "2026-08-12T08:31:14.535Z",
        "compactMetadata": {"trigger": "auto", "preTokens": 824052},
    }
    ordinary = {"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}}
    later = dict(boundary, uuid="def-456", timestamp="2026-08-13T09:00:00.000Z")

    def transcript(rows):
        handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        handle.write("\n".join(json.dumps(r) for r in rows) + "\n")
        handle.close()
        return handle.name

    def check(name, got, want):
        if got != want:
            failures.append(f"{name}: expected {want}, got {got}")

    path = transcript([ordinary, boundary, ordinary])
    uuid, meta, stamp = newest_boundary(path)
    check("finds a boundary", uuid, "abc-123")
    check("carries the trigger", meta.get("trigger"), "auto")

    path = transcript([ordinary, boundary, ordinary, later, ordinary])
    uuid, _, _ = newest_boundary(path)
    check("takes the newest of two", uuid, "def-456")

    path = transcript([ordinary, ordinary])
    uuid, _, _ = newest_boundary(path)
    check("no boundary means none", uuid, None)

    # A malformed line must not hide a real boundary on a later line.
    handle = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    handle.write('{"type":"system","subtype":"compact_boundary" BROKEN\n')
    handle.write(json.dumps(boundary) + "\n")
    handle.close()
    uuid, _, _ = newest_boundary(handle.name)
    check("a broken line does not hide a boundary", uuid, "abc-123")

    # regression, 2026-08-13: a fixed tail window was tried first and missed the
    # real boundary in this repo's own session, which sits 9 MB from the end.
    # Heavy tool output after a compaction scrolls it out of any tail.
    # The case has to be bigger than the bug it guards. At 400 entries it put
    # 1.6 MB after the boundary, so any reintroduced tail window above ~1.7 MB
    # passed it while still failing at the 9 MB the bug occurred at — and this
    # repo's own transcript carries boundaries 13.8 MB and 7.7 MB from the end
    # (panel round 1, 2026-08-18). 2,500 entries puts 10 MB after it.
    bulk = {"type": "user", "message": {"content": "x" * 4000}}
    path = transcript([ordinary, boundary] + [bulk] * 2500)
    if Path(path).stat().st_size < 10_000_000:
        check("the far-boundary case is bigger than the bug it guards", False, True)
    uuid, _, _ = newest_boundary(path)
    check("a boundary far from the end is still found", uuid, "abc-123")

    uuid, _, err = newest_boundary("/nope/missing.jsonl")
    check("missing transcript reports", uuid, None)
    check("missing transcript explains", str(err).startswith("transcript unreadable"), True)

    text = notice(boundary["compactMetadata"], boundary["timestamp"])
    check("notice names the master", "memory/rules.md" in text, True)
    check("notice gives the size", "824,052" in text, True)
    check("notice says it is not a stop signal", "not a reason to stop" in text, True)

    # run_check itself — the whole hook — had no test. Everything above tests
    # its helpers, so the notice and its dedup could both be broken with the
    # suite green (audit round three).
    import io
    import os
    import tempfile
    from contextlib import redirect_stdout

    def drive(payload):
        saved = sys.stdin
        sys.stdin = io.StringIO(json.dumps(payload))
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                run_check()
        finally:
            sys.stdin = saved
        return buffer.getvalue()

    checks = 11
    with tempfile.TemporaryDirectory() as tmp:
        log = pathlib.Path(tmp) / "t.jsonl"
        log.write_text(json.dumps(boundary) + "\n", encoding="utf-8")
        held = os.environ.get("TMPDIR")
        os.environ["TMPDIR"] = tmp     # state_path reads TMPDIR; keep it sandboxed
        try:
            first = drive({"transcript_path": str(log), "session_id": "s1"})
            checks += 1
            if "additionalContext" not in first:
                failures.append("run_check sent no notice for a real boundary")
            checks += 1
            if first.count("{") and first.strip().count("\n") > 0:
                failures.append("run_check printed more than one JSON document")
            checks += 1
            try:
                json.loads(first)
            except ValueError as exc:
                failures.append("run_check printed something that is not one JSON "
                                "document: %s" % exc)
            second = drive({"transcript_path": str(log), "session_id": "s1"})
            checks += 1
            if second.strip():
                failures.append("run_check announced the same boundary twice")
            checks += 1
            if "did not run" not in drive({"session_id": "s1"}):
                failures.append("run_check stayed silent with no transcript in the payload")

            # The branch where the marker cannot be written. Every drive above
            # runs with TMPDIR pointing at a writable temp directory, so the
            # OSError arm was never entered: the one-document guard could only
            # ever watch the happy path, and reverting the fix it commemorates
            # left the suite green (panel round 1, 2026-08-18).
            os.environ["TMPDIR"] = str(pathlib.Path(tmp) / "nowhere" / "deeper")
            try:
                stuck = drive({"transcript_path": str(log), "session_id": "s-unwritable"})
            finally:
                os.environ["TMPDIR"] = tmp
            checks += 1
            try:
                one = json.loads(stuck)
            except ValueError as exc:
                one = None
                failures.append("with the marker unwritable, run_check printed something that "
                                "is not one JSON document: %s" % exc)
            checks += 1
            if one is not None and "additionalContext" not in json.dumps(one):
                failures.append("with the marker unwritable, the compaction notice was lost")
            checks += 1
            if one is not None and "may repeat" not in one.get("systemMessage", ""):
                failures.append("with the marker unwritable, the warning that the notice may "
                                "repeat was not sent")
        finally:
            if held is None:
                os.environ.pop("TMPDIR", None)
            else:
                os.environ["TMPDIR"] = held

    for line in failures:
        print("FAIL " + line)
    print(f"compaction selftest: {checks} checks, {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(run_selftest())
    if "--check" in sys.argv:
        sys.exit(run_check())
    print(__doc__)
    sys.exit(0)
