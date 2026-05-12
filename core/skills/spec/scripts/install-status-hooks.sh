#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATUS_SCRIPT="$SCRIPT_DIR/spec-status.py"
INCLUDE_PRE_PUSH="no"
FORCE="no"

usage() {
    cat <<'EOF'
Usage: install-status-hooks.sh [--include-pre-push] [--force]

Installs local git hooks that regenerate specs/STATUS.md from per-spec
STATUS.md files. Hooks are local to this checkout and never stage or commit
generated output.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --include-pre-push)
            INCLUDE_PRE_PUSH="yes"
            ;;
        --force)
            FORCE="yes"
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: unknown argument $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

if [[ ! -f "$STATUS_SCRIPT" ]]; then
    echo "Error: missing spec-status.py next to this installer" >&2
    exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_DIR="$(git rev-parse --git-path hooks)"
mkdir -p "$HOOKS_DIR"

write_hook() {
    local hook_name="$1"
    local hook_path="$HOOKS_DIR/$hook_name"

    if [[ -f "$hook_path" ]] && ! grep -q "agentspec spec-status hook" "$hook_path"; then
        if [[ "$FORCE" != "yes" ]]; then
            echo "Error: $hook_path exists and is not an agentspec hook; use --force to replace it" >&2
            exit 1
        fi
    fi

    cat > "$hook_path" <<EOF
#!/usr/bin/env bash
# agentspec spec-status hook
set -euo pipefail

python3 "$STATUS_SCRIPT" --specs-dir "$REPO_ROOT/specs" --write --quiet
EOF
    chmod +x "$hook_path"
    echo "Installed $hook_path"
}

write_hook post-commit
write_hook post-merge
write_hook post-checkout

if [[ "$INCLUDE_PRE_PUSH" == "yes" ]]; then
    write_hook pre-push
fi
