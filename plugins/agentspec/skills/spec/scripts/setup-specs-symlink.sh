#!/usr/bin/env bash
set -euo pipefail

SPECS_ROOT="${AGENTSPEC_SPECS_ROOT:-$HOME/Documents/specs}"

usage() {
    cat <<'USAGE'
Usage: setup-specs-symlink.sh [repo-slug]

Creates a repo-local specs symlink that points at a private per-repo specs
directory. Defaults to ~/Documents/specs/<repo-name>.

Environment:
  AGENTSPEC_SPECS_ROOT  Override the private specs root.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

# Determine if we're running as a git hook (e.g., post-checkout)
# A post-checkout hook receives 3 arguments: <prev-HEAD> <new-HEAD> <flag>
REPO_SLUG_ARG=""
if [[ $# -eq 3 && ( "$3" == "0" || "$3" == "1" ) ]]; then
    # For post-checkout hooks, we only care about branch checkouts (flag = 1)
    # which includes git worktree add.
    if [[ "$3" == "0" ]]; then
        exit 0
    fi
elif [[ $# -ge 1 ]]; then
    # Manual execution with a slug
    REPO_SLUG_ARG="$1"
fi

# Find the main repo root, even if we are in a worktree
MAIN_REPO_ROOT="$(dirname "$(cd "$(git rev-parse --git-common-dir)" && pwd)")"
REPO_NAME="$(basename "$MAIN_REPO_ROOT")"
REPO_SLUG="${REPO_SLUG_ARG:-$REPO_NAME}"

WORKTREE_ROOT="$(git rev-parse --show-toplevel)"
TARGET_DIR="$SPECS_ROOT/$REPO_SLUG"
LINK_PATH="$WORKTREE_ROOT/specs"
GITIGNORE="$WORKTREE_ROOT/.gitignore"

mkdir -p "$TARGET_DIR"

if [[ ! -e "$GITIGNORE" ]]; then
    printf 'specs\n' > "$GITIGNORE"
elif ! grep -qxF specs "$GITIGNORE"; then
    printf '\nspecs\n' >> "$GITIGNORE"
fi

if [[ -L "$LINK_PATH" ]]; then
    CURRENT_TARGET="$(readlink "$LINK_PATH")"
    if [[ "$CURRENT_TARGET" == "$TARGET_DIR" ]]; then
        echo "specs -> $TARGET_DIR"
        exit 0
    fi
    ln -sfn "$TARGET_DIR" "$LINK_PATH"
    echo "specs -> $TARGET_DIR"
    exit 0
fi

if [[ -e "$LINK_PATH" ]]; then
    echo "Refusing to replace existing non-symlink specs path: $LINK_PATH" >&2
    exit 1
fi

ln -s "$TARGET_DIR" "$LINK_PATH"
echo "specs -> $TARGET_DIR"
