#!/bin/sh
# Global git-hook dispatcher, symlinked by scripts/install.sh under every
# client-side hook name in ~/.config/git/hooks (global core.hooksPath).
#
# Claude sessions link a fresh worktree's shared dirs via hooks.json events,
# but Codex and plain `git worktree add` never load plugin hooks. Git is the
# one layer every tool passes through, so the linking rides post-checkout.
#
# core.hooksPath replaces a repo's .git/hooks wholesale — no fallthrough —
# and those hold real hooks (the pre-commit framework, git-lfs). So first
# re-run the repo's own hook of the same name, propagating its exit code and
# stdin, then layer the worktree linking on top.

hook_name=$(basename "$0")
common_dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)

if [ -n "$common_dir" ] && [ -x "$common_dir/hooks/$hook_name" ]; then
  "$common_dir/hooks/$hook_name" "$@" || exit $?
fi

case "$hook_name" in
post-checkout)
  # $3=1 marks a branch checkout — `git worktree add` fires exactly that.
  [ "${3:-}" = "1" ] || exit 0
  # $0 is the ~/.config symlink; the linker lives beside the real file.
  linker="$(dirname "$(readlink -f "$0")")/symlink-worktree-shared-dirs.sh"
  [ -x "$linker" ] && "$linker" </dev/null
  ;;
esac

exit 0
