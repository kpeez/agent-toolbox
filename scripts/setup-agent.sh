#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$HOME/.agents/skills"

# copy all skills to the canonical location
rm -rf "$SKILLS_DIR"
mkdir -p "$SKILLS_DIR"
for skill_dir in "$ROOT_DIR"/core/skills/*/; do
    [[ -f "$skill_dir/SKILL.md" ]] && cp -R "${skill_dir%/}" "$SKILLS_DIR/"
done
echo "skills → $SKILLS_DIR"

install_provider() {
    local provider="$1" home_dir="$2" filename="$3"
    mkdir -p "$home_dir"
    cp "$ROOT_DIR/core/AGENTS.md" "$home_dir/$filename"
    echo "$provider → $home_dir/$filename"
}

install_provider codex   "$HOME/.codex"   AGENTS.md
install_provider claude  "$HOME/.claude"  CLAUDE.md
install_provider antigravity "$HOME/.gemini" AGENTS.md
install_provider copilot "$HOME/.copilot" copilot-instructions.md

read -r -p "Install local-model subagents and create ollama Modelfiles? [y/N] " reply
if [[ "${reply}" =~ ^[Yy]$ ]]; then
    mkdir -p "$HOME/.codex/agents"
    rm -f "$HOME/.codex/agents/gemini-analyzer.toml"
    for agent in "$ROOT_DIR"/providers/codex/agents/*.toml; do
        \cp "$agent" "$HOME/.codex/agents/"
    done
    echo "codex agents → $HOME/.codex/agents/"
    bash "$ROOT_DIR/providers/codex/create-modelfiles.sh"
fi
