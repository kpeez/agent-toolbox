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

REPO_ROOT="$(git rev-parse --show-toplevel)"
REPO_NAME="$(basename "$REPO_ROOT")"
REPO_SLUG="${1:-$REPO_NAME}"
TARGET_DIR="$SPECS_ROOT/$REPO_SLUG"
LINK_PATH="$REPO_ROOT/specs"
GITIGNORE="$REPO_ROOT/.gitignore"

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
