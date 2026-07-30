#!/bin/sh
# Recreate the gitignored `docs/agents` symlink inside a git worktree.
#
# Repos here keep `docs/agents` as a gitignored symlink to an out-of-tree
# vault. `git worktree add` never materializes gitignored paths, so a fresh
# worktree has no `docs/agents` and an agent working there reads nothing.
#
# Every exit path is 0: this hook must never fail a session.

set -u

top=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
[ -n "$top" ] || exit 0

# Already present (including as a broken symlink this script does not own).
if [ -e "$top/docs/agents" ] || [ -L "$top/docs/agents" ]; then
  exit 0
fi

# Where the shared repo state lives => the main worktree. Single-value query,
# unlike parsing `git worktree list --porcelain` (which leans on "main is
# listed first" and needs multi-line parsing). Needs git >= 2.31.
common_dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || exit 0
main=$(dirname "$common_dir")
[ "$main" != "$top" ] || exit 0

# Nothing to mirror, or the repo committed a real directory.
[ -L "$main/docs/agents" ] || exit 0

target=$(readlink "$main/docs/agents") || exit 0
[ -n "$target" ] || exit 0
# BSD readlink has no -f. A relative target resolves against the directory
# holding the link; copied verbatim it would break at the worktree's depth.
case "$target" in
  /*) ;;
  *) target="$main/docs/$target" ;;
esac

mkdir -p "$top/docs" || exit 0
ln -s "$target" "$top/docs/agents" || exit 0

# A link git would track leaks out-of-tree vault paths into the next commit.
# The pre-hook state (no docs/agents) is strictly safer, so fail back to it.
if ! git -C "$top" check-ignore -q docs/agents; then
  unlink "$top/docs/agents"
  echo "link-docs-agents: docs/agents is not gitignored in $top; link removed" >&2
fi

exit 0
