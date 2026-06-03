#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$HOME/.agents/skills"

# copy all skills to the canonical location (preserves skills not owned by this repo)
mkdir -p "$SKILLS_DIR"
for skill_dir in "$ROOT_DIR"/plugins/agentspec/skills/*/; do
    [[ -f "$skill_dir/SKILL.md" ]] && cp -R "${skill_dir%/}" "$SKILLS_DIR/"
done
echo "skills → $SKILLS_DIR"

# symlink skills for antigravity-cli
mkdir -p "$HOME/.gemini/antigravity-cli"
rm -rf "$HOME/.gemini/antigravity-cli/skills"
ln -s "$SKILLS_DIR" "$HOME/.gemini/antigravity-cli/skills"
echo "antigravity skills → $HOME/.gemini/antigravity-cli/skills"

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
for agent in "$ROOT_DIR"/plugins/agentspec/agents/*.toml; do
    cp "$agent" "$HOME/.codex/agents/"
done
echo "codex agents → $HOME/.codex/agents/"

# short PATH commands for the delegating-work skill's scripts. Symlinks point at the
# installed skill copy (no drift); the skill also documents the full path as a fallback.
BIN_DIR="$HOME/.agents/bin"
mkdir -p "$BIN_DIR"
ln -sf "$SKILLS_DIR/delegating-work/scripts/local-explore.py" "$BIN_DIR/local-explore"
ln -sf "$SKILLS_DIR/delegating-work/scripts/ext-subagent.py" "$BIN_DIR/ext-subagent"
ln -sf "$ROOT_DIR/scripts/cc-statusline.py" "$BIN_DIR/cc-statusline"
echo "scripts → $BIN_DIR/{local-explore,ext-subagent,cc-statusline} (ensure $BIN_DIR is on your PATH)"

read -r -p "Create ollama Modelfiles? [y/N] " reply
if [[ "${reply}" =~ ^[Yy]$ ]]; then
    bash "$ROOT_DIR/scripts/create-modelfiles.sh"
fi
