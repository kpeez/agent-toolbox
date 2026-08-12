#!/bin/sh
# Global git hook (core.hooksPath), symlinked under every hook name by
# scripts/install.sh. core.hooksPath makes git skip .git/hooks entirely,
# so run the repo's own hook first, then link worktree dirs on checkout.

hook_name=$(basename "$0")
common_dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)

if [ -n "$common_dir" ] && [ -x "$common_dir/hooks/$hook_name" ]; then
  "$common_dir/hooks/$hook_name" "$@" || exit $?
fi

# $3=1 means a branch checkout, which is what `git worktree add` fires
if [ "$hook_name" = "post-checkout" ] && [ "${3:-}" = "1" ]; then
  "$(dirname "$(readlink -f "$0")")/symlink-worktree-shared-dirs.sh" </dev/null
fi

exit 0
