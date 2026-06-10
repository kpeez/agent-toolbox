#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

# Codex subagents:
# Codex plugins deliver skills but not agents, so the .toml
# agents in the plugin payload must be installed into Codex's agent directory.
mkdir -p "$HOME/.codex/agents"
for agent in "$ROOT_DIR"/plugins/knack/agents/*.toml; do
    cp "$agent" "$HOME/.codex/agents/"
done
echo "codex agents → $HOME/.codex/agents/"

# statusline helper (delegating-work scripts need no install — the skill runs them via uv)
BIN_DIR="$HOME/.agents/bin"
mkdir -p "$BIN_DIR"
ln -sf "$ROOT_DIR/scripts/cc-statusline.py" "$BIN_DIR/cc-statusline"
echo "cc-statusline → $BIN_DIR/cc-statusline (ensure $BIN_DIR is on your PATH)"

read -r -p "Create ollama Modelfiles? [y/N] " reply
if [[ "${reply}" =~ ^[Yy]$ ]]; then
    bash "$ROOT_DIR/scripts/create-modelfiles.sh"
fi
