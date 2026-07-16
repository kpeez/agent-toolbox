#!/usr/bin/env bash
# PostToolUse hook: format and lint the edited Python file.
# No-ops silently unless the edit targets a .py file in a uv/ruff project,
# so it stays inert for users whose projects don't opt into this toolchain.
set -euo pipefail

file=$(jq -r '.tool_input.file_path // empty')
[ -n "$file" ] || exit 0
case "$file" in *.py) ;; *) exit 0 ;; esac

# Opt-in guards: only act in a git repo that actually uses uv + ruff.
root=$(git -C "$(dirname "$file")" rev-parse --show-toplevel 2>/dev/null) || exit 0
command -v uv >/dev/null 2>&1 || exit 0
grep -q "\[tool.ruff\]" "$root/pyproject.toml" 2>/dev/null || exit 0

cd "$root"
uv run ruff format "$file"
uv run ruff check "$file" || exit 2   # exit 2 => feed failures back to Claude
