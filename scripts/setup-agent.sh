#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"


################################################################################
# Retire stale llmOS symlinks (superseded by the llmos plugin)
################################################################################
# maintain-llmos is dissolved and setup-llmos now ships in plugins/llmos,
# installed via the plugin marketplace -- left in place these symlinks would
# double-list the skill or resurrect deleted vault code. NEVER remove
# ~/.codex/hooks.json here: that symlink is the current working Codex hook
# path and only retires once Codex plugin hooks are verified (issue #16).
for stale in \
    "$HOME/.claude/skills/maintain-llmos" \
    "$HOME/.claude/skills/setup-llmos" \
    "$HOME/.codex/skills/setup-llmos"; do
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

################################################################################
# Ollama model install
################################################################################
read -r -p "Create ollama Modelfiles? [y/N] " reply
if [[ "${reply}" =~ ^[Yy]$ ]]; then
    bash "$ROOT_DIR/scripts/create-modelfiles.sh"
fi
