#!/usr/bin/env bash
set -euo pipefail

# update_agentspecs.sh - sync agentspecs to all AI agent CLI configs
#
# Supports:
#   - Claude Code (~/.claude/)
#   - OpenAI Codex CLI (~/.codex/) - must copy skills (ignores symlinks)
#   - Google Gemini CLI (~/.gemini/)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # no color

log() { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
info() { echo -e "${BLUE}→${NC} $1"; }

# check source files exist
if [[ ! -f "$SCRIPT_DIR/AGENTS.md" ]]; then
    echo "Error: AGENTS.md not found in $SCRIPT_DIR"
    exit 1
fi

if [[ ! -d "$SCRIPT_DIR/skills" ]]; then
    echo "Error: skills/ directory not found in $SCRIPT_DIR"
    exit 1
fi

echo "Updating agentspecs from: $SCRIPT_DIR"
echo ""

# --- Claude Code ---
CLAUDE_DIR="$HOME/.claude"
if [[ -d "$CLAUDE_DIR" ]] || mkdir -p "$CLAUDE_DIR" 2>/dev/null; then
    info "Claude Code ($CLAUDE_DIR)"

    # instructions
    cp "$SCRIPT_DIR/AGENTS.md" "$CLAUDE_DIR/CLAUDE.md"
    log "AGENTS.md → CLAUDE.md"

    # skills (can use symlink or copy - symlink for easy updates)
    rm -rf "$CLAUDE_DIR/skills"
    cp -r "$SCRIPT_DIR/skills" "$CLAUDE_DIR/skills"
    log "Copied skills/ → skills/"
    echo ""
fi

# --- OpenAI Codex CLI ---
CODEX_DIR="$HOME/.codex"
if [[ -d "$CODEX_DIR" ]] || mkdir -p "$CODEX_DIR" 2>/dev/null; then
    info "Codex CLI ($CODEX_DIR)"

    # instructions
    cp "$SCRIPT_DIR/AGENTS.md" "$CODEX_DIR/AGENTS.md"
    log "AGENTS.md → AGENTS.md"

    # skills (must copy - Codex ignores symlinks)
    rm -rf "$CODEX_DIR/skills"
    cp -r "$SCRIPT_DIR/skills" "$CODEX_DIR/skills"
    log "Copied skills/ → skills/"

    echo ""
fi

# --- Google Gemini CLI ---
GEMINI_DIR="$HOME/.gemini"
if [[ -d "$GEMINI_DIR" ]] || mkdir -p "$GEMINI_DIR" 2>/dev/null; then
    info "Gemini CLI ($GEMINI_DIR)"

    # instructions
    cp "$SCRIPT_DIR/AGENTS.md" "$GEMINI_DIR/GEMINI.md"
    log "AGENTS.md → GEMINI.md"

    # skills (Gemini supports SKILL.md format - symlink for easy updates)
    rm -rf "$GEMINI_DIR/skills"
    cp -r "$SCRIPT_DIR/skills" "$GEMINI_DIR/skills"
    log "Copied skills/ → skills/"
    echo ""
fi

echo "Done. Run this script again after updating agentspecs."
