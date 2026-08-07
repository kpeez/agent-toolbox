#!/usr/bin/env bash
# PreToolUse hook: refuse to publish agent attribution.
#
# ship-pr already forbids it in prose, but prose is advisory and the footers are
# appended reflexively -- a session URL or "Generated with Claude Code" in a
# commit message is unrewritable once pushed. This is the deterministic gate:
# it blocks the call instead of stripping the line, so the agent rewrites the
# text itself rather than having its message silently edited underneath it.
set -euo pipefail

command_text=$(jq -r '.tool_input.command // ""')
[ -n "$command_text" ] || exit 0

# Only publishing verbs are inspected. Without this, a `curl claude.ai/...` or a
# grep over this very file would trip the guard.
case "$command_text" in
  *"git commit"*|*"git tag"*|*"gh pr "*|*"gh issue "*|*"gh stack "*) ;;
  *) exit 0 ;;
esac

# A body passed by file is invisible in the command string, so read it too.
subject=$command_text
body_file=$(printf '%s' "$command_text" | sed -n 's/.*--body-file[= ]*\([^ ]*\).*/\1/p')
if [ -n "$body_file" ] && [ -f "$body_file" ]; then
  subject="$subject
$(cat "$body_file")"
fi

banned='claude\.ai/|claude\.com/|[Cc]o-[Aa]uthored-[Bb]y:.*([Cc]laude|[Aa]nthropic)|[Gg]enerated with.*[Cc]laude|🤖'
hit=$(printf '%s' "$subject" | grep -oEm1 "$banned" || true)
[ -n "$hit" ] || exit 0

cat >&2 <<MSG
Blocked: this commit or pull request carries agent attribution ("$hit").

Session URLs, Co-authored-by trailers naming Claude or Anthropic, "Generated
with" footers, and 🤖 never appear in commit messages, PR titles, or PR bodies.
Rewrite the text without that line and run the command again.
MSG
exit 2
