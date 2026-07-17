#!/usr/bin/env bash

set -u

failures=0
root_valid=false
root_repair='Run /setup-llmos, or set it manually: export LLMOS_ROOT="/absolute/path/to/llmOS"'
qmd_repair='npm install -g @tobilu/qmd'
config_path="$HOME/.config/llmos/config.json"

# Repairs are platform-specific. Override detection with LLMOS_DOCTOR_OS in tests.
case "${LLMOS_DOCTOR_OS:-$(uname -s)}" in
  Darwin)
    platform=macos
    obsidian_repair='brew install --cask obsidian && ln -sfh "/Applications/Obsidian.app/Contents/MacOS/obsidian-cli" "$(brew --prefix)/bin/obsidian-cli"'
    ;;
  Linux)
    # Linux ships the CLI as `obsidian`; expose it under the canonical name with a shim.
    platform=linux
    obsidian_repair='sudo snap install obsidian --classic && mkdir -p "$HOME/.local/bin" && printf '\''#!/usr/bin/env bash\nexec obsidian "$@"\n'\'' > "$HOME/.local/bin/obsidian-cli" && chmod +x "$HOME/.local/bin/obsidian-cli"'
    ;;
  *)
    printf 'FAIL platform: setup-llmos supports macOS and Linux only\n'
    exit 1
    ;;
esac

# Resolution: $LLMOS_ROOT -> ~/.config/llmos/config.json (key "vault_root") -> fail loud.
# No branch derives the root from this script's own location (ADR-0001).
if [[ -n "${LLMOS_ROOT:-}" ]]; then
  root_input=$LLMOS_ROOT
elif [[ -f "$config_path" ]]; then
  root_input=$(python3 -c '
import json, sys
try:
    print(json.load(open(sys.argv[1]))["vault_root"])
except Exception:
    pass
' "$config_path")
else
  root_input=""
fi

if [[ -z "$root_input" ]]; then
  printf 'FAIL vault-root: llmOS root is not configured\n'
  printf 'REPAIR %s\n' "$root_repair"
  failures=$((failures + 1))
  resolved_root=""
else
  root_input=${root_input/#\~/$HOME}
  if [[ -d "$root_input" ]]; then
    resolved_root=$(CDPATH= cd -- "$root_input" && pwd -P)
  else
    resolved_root=$root_input
  fi

  if [[ -d "$resolved_root/.obsidian" && -f "$resolved_root/llmOS.md" ]]; then
    root_valid=true
    printf 'PASS vault-root: %s\n' "$resolved_root"
  else
    printf 'FAIL vault-root: %s is not an llmOS vault with .obsidian/ and llmOS.md\n' "$resolved_root"
    printf 'REPAIR %s\n' "$root_repair"
    failures=$((failures + 1))
  fi
fi

if [[ "$platform" == macos ]]; then
  obsidian_app_repair="open -a Obsidian \"$resolved_root\""
else
  obsidian_app_repair="obsidian \"$resolved_root\""
fi

obsidian_cli=$(command -v obsidian-cli 2>/dev/null || true)
if [[ -n "$obsidian_cli" ]]; then
  printf 'PASS obsidian-cli: %s\n' "$obsidian_cli"
else
  printf 'FAIL obsidian-cli: command not found\n'
  printf 'REPAIR %s\n' "$obsidian_repair"
  failures=$((failures + 1))
fi

if [[ -n "$obsidian_cli" && "$root_valid" == true ]]; then
  if obsidian_output=$("$obsidian_cli" 'vault=llmOS' read 'path=llmOS.md' 2>&1); then
    expected_sentinel=$(<"$resolved_root/llmOS.md")
    if [[ "$obsidian_output" == "$expected_sentinel" ]]; then
      printf 'PASS obsidian-vault: read canonical llmOS.md\n'
    else
      printf 'FAIL obsidian-vault: llmOS.md content does not match %s/llmOS.md\n' "$resolved_root"
      printf 'REPAIR %s\n' "$obsidian_app_repair"
      if [[ "$platform" == linux ]]; then
        printf 'NOTE enable Settings > General > Advanced > Command line interface\n'
      fi
      failures=$((failures + 1))
    fi
  else
    printf 'FAIL obsidian-vault: Obsidian app or vault llmOS is unavailable: %s\n' "$obsidian_output"
    printf 'REPAIR %s\n' "$obsidian_app_repair"
    if [[ "$platform" == linux ]]; then
      printf 'NOTE enable Settings > General > Advanced > Command line interface\n'
    fi
    failures=$((failures + 1))
  fi
else
  printf 'FAIL obsidian-vault: blocked by vault-root or obsidian-cli failure\n'
  if [[ "$root_valid" != true ]]; then
    printf 'REPAIR %s\n' "$root_repair"
  else
    printf 'REPAIR %s\n' "$obsidian_repair"
  fi
  failures=$((failures + 1))
fi

qmd_cli=$(command -v qmd 2>/dev/null || true)
if [[ -n "$qmd_cli" ]]; then
  printf 'PASS qmd: %s\n' "$qmd_cli"
else
  printf 'FAIL qmd: command not found\n'
  printf 'REPAIR %s\n' "$qmd_repair"
  failures=$((failures + 1))
fi

collection_matches=false
collection_repair=$qmd_repair
if [[ -n "$qmd_cli" && "$root_valid" == true ]]; then
  if collection_output=$("$qmd_cli" collection show llmos 2>&1); then
    collection_path=$(printf '%s\n' "$collection_output" | awk -F ':[[:space:]]*' '/^[[:space:]]*Path:/ { sub(/^[[:space:]]*/, "", $2); print $2; exit }')
    if [[ -n "$collection_path" && -d "$collection_path" ]]; then
      collection_root=$(CDPATH= cd -- "$collection_path" && pwd -P)
    else
      collection_root=$collection_path
    fi

    if [[ -n "$collection_root" && "$collection_root" == "$resolved_root" ]]; then
      collection_matches=true
      printf 'PASS qmd-collection: llmos -> %s\n' "$collection_root"
    else
      printf 'FAIL qmd-collection: llmos points to %s, expected %s\n' "${collection_root:-an unreadable path}" "$resolved_root"
      collection_repair=$(printf 'qmd collection remove llmos && qmd collection add "%s" --name llmos' "$resolved_root")
      printf 'REPAIR %s\n' "$collection_repair"
      failures=$((failures + 1))
    fi
  else
    printf 'FAIL qmd-collection: llmos collection is missing: %s\n' "$collection_output"
    collection_repair=$(printf 'qmd collection add "%s" --name llmos' "$resolved_root")
    printf 'REPAIR %s\n' "$collection_repair"
    failures=$((failures + 1))
  fi
else
  printf 'FAIL qmd-collection: blocked by vault-root or qmd failure\n'
  if [[ "$root_valid" != true ]]; then
    collection_repair=$root_repair
  else
    collection_repair=$qmd_repair
  fi
  printf 'REPAIR %s\n' "$collection_repair"
  failures=$((failures + 1))
fi

if [[ "$collection_matches" == true ]]; then
  if qmd_ls_output=$("$qmd_cli" ls llmos/llmOS.md 2>&1); then
    if [[ "$qmd_ls_output" == *"qmd://llmos/llmOS.md"* || "$qmd_ls_output" == *"qmd://llmos/llmos.md"* ]] \
      && [[ "$qmd_ls_output" != *"No files found"* && "$qmd_ls_output" != *"no files found"* ]]; then
      printf 'PASS qmd-index: llmOS.md is indexed\n'
    else
      printf 'FAIL qmd-index: llmOS.md is stale or unindexed\n'
      printf 'REPAIR qmd update\n'
      failures=$((failures + 1))
    fi
  else
    printf 'FAIL qmd-index: qmd could not inspect llmOS.md: %s\n' "$qmd_ls_output"
    printf 'REPAIR qmd status\n'
    failures=$((failures + 1))
  fi

  if qmd_get_output=$("$qmd_cli" get qmd://llmos/llmOS.md --no-line-numbers 2>&1); then
    if [[ "$qmd_get_output" == qmd://* ]]; then
      retrieved_sentinel=$(printf '%s\n' "$qmd_get_output" | awk '
        !header && /^---$/ { header=1; next }
        header && !content && /^$/ { next }
        header { content=1; print }
      ')
    else
      retrieved_sentinel=$qmd_get_output
    fi
    expected_sentinel=$(<"$resolved_root/llmOS.md")
    if [[ "$retrieved_sentinel" == "$expected_sentinel" ]]; then
      printf 'PASS qmd-retrieval: full llmOS.md matches the vault\n'
    else
      printf 'FAIL qmd-retrieval: retrieved llmOS.md does not match the vault sentinel\n'
      printf 'REPAIR qmd update\n'
      failures=$((failures + 1))
    fi
  else
    printf 'FAIL qmd-retrieval: qmd could not retrieve qmd://llmos/llmOS.md: %s\n' "$qmd_get_output"
    printf 'REPAIR qmd update\n'
    failures=$((failures + 1))
  fi
else
  printf 'FAIL qmd-index: blocked by qmd-collection failure\n'
  printf 'REPAIR %s\n' "$collection_repair"
  failures=$((failures + 1))
  printf 'FAIL qmd-retrieval: blocked by qmd-collection failure\n'
  printf 'REPAIR %s\n' "$collection_repair"
  failures=$((failures + 1))
fi

if ((failures > 0)); then
  exit 1
fi
