#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"


################################################################################
# Retire stale llmOS symlinks (superseded by the llmos plugin)
################################################################################
# maintain-llmos is dissolved and setup-llmos now ships in plugins/llmos,
# installed via the plugin marketplace -- left in place these symlinks would
# double-list the skill or resurrect deleted vault code.
#
# Both hook symlinks are now dead and are removed here (issue #16). An earlier
# note here said ~/.codex/hooks.json must never be removed because it was "the
# current working Codex hook path" -- that is no longer true, and had not been
# for a while: its target (the vault's agents/codex/hooks.json) was deleted
# when the vault's agents/ tree went away, so the link dangles and Codex has
# been running with zero hooks. ~/.claude/hooks/llmos_hook.py resolves, but
# nothing invokes it since the settings.json SessionStart block that named it
# was removed; the llmos plugin now provides that hook via ${CLAUDE_PLUGIN_ROOT}.
for stale in \
    "$HOME/.claude/skills/maintain-llmos" \
    "$HOME/.claude/skills/setup-llmos" \
    "$HOME/.codex/skills/setup-llmos" \
    "$HOME/.codex/hooks.json" \
    "$HOME/.claude/hooks/llmos_hook.py"; do
    [[ -L "$stale" ]] && rm "$stale"
done
echo "removed stale llmOS symlinks (if present)"


################################################################################
# Claude
################################################################################
mkdir -p "$HOME/.claude"
cp "$ROOT_DIR/AGENTS.md" "$HOME/.claude/CLAUDE.md"

# statusline helper (delegating-work scripts need no install — the skill runs them via uv)
cp "$ROOT_DIR/scripts/cc_statusline.py" "$HOME/.claude/"
echo "claude instructions + statusline → $HOME/.claude/"

# Wire settings.json to the statusline we just installed. Copying the script was never
# enough on its own: settings.json is what actually names the command, so an install that
# only dropped the file left the statusline unwired (or pinned to an older path we no
# longer update). Ours replaces any command naming a path we have shipped; a statusline
# pointing anywhere else is the user's own and is left alone.
python3 - "$HOME/.claude/settings.json" <<'PY'
import json
import os
import sys

# realpath first: settings.json is often a symlink into a dotfiles repo, and os.replace()
# on the link path would silently swap the link for a regular file.
path = os.path.realpath(sys.argv[1])
command = "python3 ~/.claude/cc_statusline.py"
SHIPPED = ("cc_statusline.py", "statusline.py", "statusline-command.sh")

settings = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            settings = json.load(f)
    except json.JSONDecodeError as exc:
        settings = None
        print(f"settings.json is not valid JSON ({exc}) — left untouched, statusline unwired")
    if not isinstance(settings, dict):
        sys.exit(0)

current = settings.get("statusLine")
current_cmd = current.get("command", "") if isinstance(current, dict) else ""
if current is not None and not any(name in current_cmd for name in SHIPPED):
    print(f"kept your statusLine ({current_cmd or current!r}) — unset it to use ours")
    sys.exit(0)

settings["statusLine"] = {"type": "command", "command": command}
tmp = f"{path}.tmp"
with open(tmp, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
os.replace(tmp, path)
print(f"statusLine → {command}")
PY


################################################################################
# Codex
################################################################################
# Subagents:
# Codex plugins deliver skills but not agents, so the .toml
# agents in the plugin payload must be installed into Codex's agent directory.
mkdir -p "$HOME/.codex/agents"
for agent in "$ROOT_DIR"/plugins/knack/agents/*.toml; do
    cp "$agent" "$HOME/.codex/agents/"
done
echo "codex agents → $HOME/.codex/agents/"


################################################################################
# Unpackaged skills (skills/ — not part of any plugin)
################################################################################
# symlink each skill straight from the repo into Claude's and Codex's personal
# skills directories (single source, no copies)
for skill_dir in "$ROOT_DIR"/skills/*/; do
    [[ -f "$skill_dir/SKILL.md" ]] || continue
    name="$(basename "$skill_dir")"
    for target in "$HOME/.claude/skills" "$HOME/.codex/skills"; do
        mkdir -p "$target"
        rm -rf "${target:?}/$name"
        ln -s "${skill_dir%/}" "$target/$name"
    done
done
echo "unpackaged skills → $HOME/.claude/skills/, $HOME/.codex/skills/"


################################################################################
# Antigravity
################################################################################
# antigravity skills: symlink each skill straight from the repo (single source, no copies)
AGY_SKILLS="$HOME/.gemini/antigravity-cli/skills"
rm -rf "$AGY_SKILLS"
mkdir -p "$AGY_SKILLS"
for skill_dir in "$ROOT_DIR"/plugins/*/skills/*/; do
    [[ -f "$skill_dir/SKILL.md" ]] && ln -s "${skill_dir%/}" "$AGY_SKILLS/"
done
echo "antigravity skills → $AGY_SKILLS"

install_provider() {
    local provider="$1" home_dir="$2" filename="$3"
    mkdir -p "$home_dir"
    cp "$ROOT_DIR/AGENTS.md" "$home_dir/$filename"
    echo "$provider → $home_dir/$filename"
}

install_provider antigravity "$HOME/.gemini" AGENTS.md
install_provider copilot "$HOME/.copilot" copilot-instructions.md
