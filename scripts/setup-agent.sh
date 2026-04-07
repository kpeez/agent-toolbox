#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log() { echo -e "${GREEN}✓${NC} $1"; }
header() { echo -e "${BOLD}${CYAN}$1${NC}"; }
field() { printf "  %-13s %s\n" "$1" "$2"; }

usage() {
    cat <<'EOF'
Usage: ./scripts/setup-agent.sh [codex|claude|gemini|copilot|all|auto]

Installs shared core assets plus provider-specific overlays into the selected
agent home directory. With no argument, auto-detect installed providers.
EOF
}

if [[ $# -gt 1 ]]; then
    usage
    exit 1
fi

TARGET="${1:-auto}"

if [[ ! -f "$ROOT_DIR/core/instructions/AGENTS.md" ]]; then
    echo "Error: missing shared instructions at core/instructions/AGENTS.md"
    exit 1
fi

if [[ ! -d "$ROOT_DIR/core/skills" ]]; then
    echo "Error: missing shared skills at core/skills"
    exit 1
fi

install_provider() {
    local provider="$1"
    local home_dir=""
    local instruction_name=""

    case "$provider" in
        codex)
            home_dir="$HOME/.codex"
            instruction_name="AGENTS.md"
            ;;
        claude)
            home_dir="$HOME/.claude"
            instruction_name="CLAUDE.md"
            ;;
        gemini)
            home_dir="$HOME/.gemini"
            instruction_name="GEMINI.md"
            ;;
        copilot)
            home_dir="$HOME/.copilot"
            instruction_name="copilot-instructions.md"
            ;;
        *)
            echo "Error: unknown provider $provider"
            exit 1
            ;;
    esac

    local provider_dir="$ROOT_DIR/providers/$provider"
    local instruction_path="$home_dir/$instruction_name"
    local skills_dir="$home_dir/skills"
    local provider_skills_dir="$provider_dir/skills"
    local provider_skill_note="shared only"

    if [[ ! -f "$provider_dir/instructions.md" ]]; then
        echo "Error: missing provider instructions at $provider_dir/instructions.md"
        exit 1
    fi

    if [[ -d "$provider_skills_dir" ]] && [[ -n "$(find "$provider_skills_dir" -mindepth 1 -maxdepth 1 2>/dev/null)" ]]; then
        provider_skill_note="shared + provider-specific"
    fi

    header "Agent Setup"
    field "Provider:" "$provider"
    field "Destination:" "$home_dir"
    field "Instructions:" "$instruction_name"
    field "Skills:" "$provider_skill_note"
    mkdir -p "$home_dir"

    cat \
        "$ROOT_DIR/core/instructions/AGENTS.md" \
        <(printf '\n\n') \
        "$provider_dir/instructions.md" \
        > "$instruction_path"
    log "Wrote $instruction_path"

    rm -rf "$skills_dir"
    mkdir -p "$skills_dir"
    cp -R "$ROOT_DIR/core/skills/." "$skills_dir/"
    log "Copied shared skills to $skills_dir"

    if [[ -d "$provider_skills_dir" ]] && [[ -n "$(find "$provider_skills_dir" -mindepth 1 -maxdepth 1 2>/dev/null)" ]]; then
        cp -R "$provider_skills_dir/." "$skills_dir/"
        log "Copied provider-specific skills to $skills_dir"
    fi

    field "Ready:" "$provider"
    echo
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

detect_provider() {
    local provider="$1"

    case "$provider" in
        codex)
            [[ -d "$HOME/.codex" ]] || command_exists codex
            ;;
        claude)
            [[ -d "$HOME/.claude" ]] || command_exists claude
            ;;
        gemini)
            [[ -d "$HOME/.gemini" ]] || command_exists gemini
            ;;
        copilot)
            [[ -d "$HOME/.copilot" ]] || command_exists copilot
            ;;
        *)
            return 1
            ;;
    esac
}

read_answer() {
    local prompt="$1"
    local default_answer="$2"
    local answer=""

    printf "%s" "$prompt" >&2
    if IFS= read -r answer; then
        if [[ -z "$answer" ]]; then
            answer="$default_answer"
        fi
    else
        answer="$default_answer"
    fi

    printf "%s" "$answer"
}

is_yes() {
    local answer
    answer="$(printf "%s" "$1" | tr '[:upper:]' '[:lower:]')"
    [[ "$answer" == "y" || "$answer" == "yes" ]]
}

run_auto_mode() {
    local detected=()
    local provider=""

    for provider in codex claude gemini copilot; do
        if detect_provider "$provider"; then
            detected+=("$provider")
        fi
    done

    if [[ ${#detected[@]} -eq 0 ]]; then
        echo "Error: no supported providers detected. Use an explicit target if needed."
        exit 1
    fi

    header "Detected Providers"
    for provider in "${detected[@]}"; do
        printf "  - %s\n" "$provider"
    done
    echo

    local answer
    answer="$(read_answer "Install all detected providers? [Y/n] " "y")"
    echo >&2
    if is_yes "$answer"; then
        for provider in "${detected[@]}"; do
            install_provider "$provider"
        done
        return
    fi

    for provider in "${detected[@]}"; do
        answer="$(read_answer "Install $provider? [y/N] " "n")"
        echo >&2
        if is_yes "$answer"; then
            install_provider "$provider"
        fi
    done
}

case "$TARGET" in
    codex|claude|gemini|copilot)
        install_provider "$TARGET"
        ;;
    all)
        install_provider codex
        install_provider claude
        install_provider gemini
        install_provider copilot
        ;;
    auto)
        run_auto_mode
        ;;
    *)
        usage
        exit 1
        ;;
esac
