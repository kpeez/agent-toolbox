#!/bin/sh
# Link the main checkout's gitignored local-resource dirs (artifacts, data,
# docs/agents) into a git worktree. `git worktree add` never materializes
# gitignored paths, so a fresh worktree is missing per-machine data and an
# agent working there climbs back out to the main checkout for it.
#
# Fires on SessionStart, SubagentStart, and PostToolUse:EnterWorktree — the
# last because Session hooks don't re-fire when EnterWorktree switches the
# session mid-turn.
#
# Every exit path is 0: this hook must never fail a session.

set -u

# EnterWorktree reports the worktree in its tool_response; other events carry
# the session cwd. With neither (manual run), fall back to the process cwd.
input=$(cat 2>/dev/null) || input=""
top=$(printf '%s' "$input" | jq -r '.tool_response.worktreePath // .cwd // empty' 2>/dev/null) || top=""
[ -n "$top" ] || top=$(pwd)
top=$(git -C "$top" rev-parse --show-toplevel 2>/dev/null) || exit 0

# Where the shared repo state lives => the main worktree. Single-value query,
# unlike parsing `git worktree list --porcelain`. Needs git >= 2.31.
common_dir=$(git -C "$top" rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || exit 0
main=$(dirname "$common_dir")
[ "$main" != "$top" ] || exit 0

for entry in artifacts data docs/agents; do
  src="$main/$entry"
  dst="$top/$entry"
  [ -e "$src" ] || continue
  if [ -e "$dst" ] || [ -L "$dst" ]; then continue; fi
  # A link git would track leaks main-checkout paths into the next commit.
  git -C "$top" check-ignore -q "$entry" || continue
  mkdir -p "$(dirname "$dst")" || continue
  ln -s "$src" "$dst" 2>/dev/null || true
done

exit 0
