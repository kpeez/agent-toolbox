#!/usr/bin/env bash
# PostToolUse hook: format and lint the Python files an edit touched.
# No-ops silently unless a target is a .py file in a uv/ruff project,
# so it stays inert for users whose projects don't opt into this toolchain.
set -euo pipefail

# Claude's Write/Edit names exactly one `file_path`. Codex's apply_patch names
# none: its targets live inside the patch envelope on `command`, one patch may
# name several, and they are relative to the session's working directory.
paths=$(jq -r '
  .tool_input // {}
  | if (.file_path // "") != "" then .file_path
    else (.command // "")
      | split("\n")[]
      | select(startswith("*** Update File:") or startswith("*** Add File:"))
      | sub("^\\*\\*\\* (Update|Add) File: *"; "")
    end
')

# Absolutize before the `cd` below, which would otherwise re-root Codex's
# relative paths against the repo top level instead of the session cwd.
files=()
while IFS= read -r path; do
  case "$path" in *.py) ;; *) continue ;; esac
  [ -f "$path" ] || continue
  files+=("$(cd "$(dirname "$path")" && pwd)/$(basename "$path")")
done <<<"$paths"
[ ${#files[@]} -gt 0 ] || exit 0

# Opt-in guards: only act in a git repo that actually uses uv + ruff.
root=$(git -C "$(dirname "${files[0]}")" rev-parse --show-toplevel 2>/dev/null) || exit 0
command -v uv >/dev/null 2>&1 || exit 0
grep -q "\[tool.ruff\]" "$root/pyproject.toml" 2>/dev/null || exit 0

cd "$root"
uv run ruff format "${files[@]}"
uv run ruff check "${files[@]}" || exit 2   # exit 2 => feed failures back to Claude
