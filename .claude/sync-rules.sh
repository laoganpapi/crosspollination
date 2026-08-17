#!/usr/bin/env bash
# Keep this repo's copy of the kit current.
#
# Runs at session start. Reads the kit's manifest from the home repo, fetches
# each file, and rewrites only the ones that differ. Anything rewritten is handed
# to the session as well, so a rule change applies in the session that finds it
# rather than the one after.
#
# Silent when already current, and silent when offline — the committed copies are
# the floor, so a failed fetch never leaves a repo without rules. The installer
# does first-time setup and wires the hooks; this keeps the files fresh after,
# because the installer refuses to overwrite files a repo tracks and a repo has
# to track them for a cloud session to see them at all.
set -u

# Overridable so the success path can be exercised against a local checkout;
# unset everywhere except tests, where the published copy would be the thing
# under test rather than the thing tested against.
RAW="${SYNC_RULES_SRC:-https://raw.githubusercontent.com/laoganpapi/Claude-Improvement/main}"
CLAUDE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$CLAUDE_DIR")"

# Never run in the home repo: the working copy here is the source, and pulling
# the published version over it destroys uncommitted rule edits. Learned the hard way.
[ -f "$ROOT/memory/map.md" ] && exit 0

fetch() { curl -sf --max-time 10 "$RAW/$1"; }

MANIFEST="$(fetch install/bundle.txt)" || exit 0
[ -z "$MANIFEST" ] && exit 0

changed=""
for rel in $(printf '%s\n' "$MANIFEST" | sed -e 's/#.*//' -e '/^[[:space:]]*$/d'); do
  new="$(fetch "$rel")" || continue          # one missing file must not stop the rest
  [ -z "$new" ] && continue
  local_file="$ROOT/$rel"
  [ -f "$local_file" ] && [ "$new" = "$(cat "$local_file")" ] && continue
  mkdir -p "$(dirname "$local_file")"
  # Atomic. This script is in the manifest and so updates itself; bash reads a
  # script incrementally, and truncating the file it is running from corrupts
  # execution mid-way. A rename swaps the inode and leaves the running copy intact.
  tmp="$local_file.sync-$$"
  printf '%s\n' "$new" > "$tmp" && chmod --reference="$local_file" "$tmp" 2>/dev/null
  mv -f "$tmp" "$local_file"
  changed="$changed $rel"
done

# Session settings the kit owns, merged rather than copied: a repo's settings.json
# also carries its hooks and anything that repo added, and those must survive.
#
# The hooks are merged here too, and that is the whole point of this block.
# install.sh wired them once at install time and nothing ever re-ran it, so the
# kit's files kept arriving here while `hooks` was left alone: measured
# 2026-08-14 across Republic-Work, Venture-Deals, Nous and Fih, every one of
# them carrying feedback.py on disk with nothing calling it. A merge the
# session-start path performs itself needs nothing re-run.
#
# One implementation, fetched rather than copied, so this and install.sh cannot
# drift into disagreeing about what a repo should carry.
kit="$(mktemp -d)" && trap 'rm -rf "$kit"' EXIT
if [ -n "${kit:-}" ] && [ -d "$kit" ] \
   && fetch install/merge-settings.py       > "$kit/merge.py" \
   && fetch .claude/settings.json           > "$kit/settings.json" \
   && fetch install/settings-fragment.json  > "$kit/fragment.json" \
   && [ -s "$kit/merge.py" ] && [ -s "$kit/settings.json" ] && [ -s "$kit/fragment.json" ]; then
  merged="$(python3 "$kit/merge.py" "$ROOT/.claude/settings.json" \
              "$kit/settings.json" "$kit/fragment.json" 2>/dev/null)" || merged=""
  [ -n "$merged" ] && changed="$changed settings.json($merged)"
fi

[ -z "$changed" ] && exit 0

rules="$ROOT/.claude/universal.md"
context=""
case "$changed" in
  *universal.md*) context="$(printf 'The universal rules were out of date here and have just been updated from the home repo. The current text follows and overrides any older copy:\n\n%s' "$(cat "$rules")")" ;;
  *) context="$(printf 'These files were out of date here and have just been updated from the home repo:%s' "$changed")" ;;
esac

python3 -c '
import json, sys
print(json.dumps({
    "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": sys.argv[1]},
    "systemMessage": "Kit updated from the home repo:" + sys.argv[2],
}))' "$context" "$changed"
