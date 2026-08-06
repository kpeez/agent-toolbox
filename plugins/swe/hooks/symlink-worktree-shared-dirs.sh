#!/bin/sh
# PostToolUse:EnterWorktree hook — link the main checkout's gitignored local
# resource dirs (artifacts, data, docs/agents) into the worktree just entered.
#
# `git worktree add` never materializes gitignored paths, so a fresh worktree
# is missing per-machine data and agents climb back out to the main checkout
# for it. SessionStart/SubagentStart hooks don't fire on a mid-session
# EnterWorktree, which is why this runs on the tool call itself.
#
# Every exit path is 0: this hook must never fail a session.

set -u

input=$(cat 2>/dev/null) || input=""
top=$(printf '%s' "$input" | jq -r '.tool_response.worktreePath // .cwd // empty' 2>/dev/null) || top=""
[ -n "$top" ] || exit 0
case "$top" in */.claude/worktrees/*) ;; *) exit 0 ;; esac

# The main worktree owns the shared repo state (see link-docs-agents.sh).
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
