#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CANONICAL_SKILLS_DIR="$HOME/.agents/skills"

GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log() { echo -e "${GREEN}✓${NC} $1"; }
header() { echo -e "${BOLD}${CYAN}$1${NC}"; }
field() { printf "  %-13s %s\n" "$1" "$2"; }

skill_count() {
    local skill_root="$1"
    local kind="${2:-all}"

    if [[ ! -d "$skill_root" ]]; then
        printf "0"
        return
    fi

    case "$kind" in
        default)
            find "$skill_root" -mindepth 2 -maxdepth 2 -name SKILL.md \
                ! -path "$skill_root/llm-wiki-*/SKILL.md" | wc -l | tr -d ' '
            ;;
        llm-wiki)
            find "$skill_root" -mindepth 2 -maxdepth 2 -name SKILL.md \
                -path "$skill_root/llm-wiki-*/SKILL.md" | wc -l | tr -d ' '
            ;;
        all)
            find "$skill_root" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' '
            ;;
        *)
            echo "Error: unknown skill count kind $kind"
            exit 1
            ;;
    esac
}

copy_core_skills() {
    local skills_dir="$1"
    local include_llm_wiki="$2"
    local skill_dir=""
    local skill_name=""

    for skill_dir in "$ROOT_DIR"/core/skills/*; do
        [[ -d "$skill_dir" ]] || continue
        [[ -f "$skill_dir/SKILL.md" ]] || continue

        skill_name="$(basename "$skill_dir")"
        if [[ "$skill_name" == llm-wiki-* ]] && [[ "$include_llm_wiki" != "yes" ]]; then
            continue
        fi

        cp -R "$skill_dir" "$skills_dir/"
    done
}

provider_uses_canonical_skills() {
    local provider="$1"

    [[ "$provider" == "copilot" ]]
}

apply_auto_approval_config() {
    local provider="$1"

    if ! command -v python3 >/dev/null 2>&1; then
        echo "Error: python3 is required to merge provider permission config"
        exit 1
    fi

    python3 "$ROOT_DIR/scripts/apply-auto-approval-configs.py" \
        --provider "$provider" \
        --home-dir "$HOME" \
        --root-dir "$ROOT_DIR" \
        >/dev/null
}

usage() {
    cat <<'EOF'
Usage: ./scripts/setup-agent.sh [codex|claude|gemini|copilot|all|auto]

Installs shared instructions and skills for the selected agent. Skills are
installed canonically into ~/.agents/skills and mirrored only for providers that
require provider-local skill directories. With no argument, auto-detect
installed providers.
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
    local include_llm_wiki="$2"
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
    local shared_skill_count=""
    local skill_note=""
    local skill_destination=""

    if [[ ! -f "$provider_dir/instructions.md" ]]; then
        echo "Error: missing provider instructions at $provider_dir/instructions.md"
        exit 1
    fi

    shared_skill_count="$(skill_count "$ROOT_DIR/core/skills" default)"
    skill_note="$shared_skill_count shared"
    if [[ "$include_llm_wiki" == "yes" ]]; then
        skill_note="$skill_note + $(skill_count "$ROOT_DIR/core/skills" llm-wiki) llm-wiki"
    fi
    if provider_uses_canonical_skills "$provider"; then
        skill_destination="$CANONICAL_SKILLS_DIR"
    else
        skill_destination="$CANONICAL_SKILLS_DIR + $skills_dir mirror"
    fi

    header "Agent Setup"
    field "Provider:" "$provider"
    field "Destination:" "$home_dir"
    field "Instructions:" "$instruction_name"
    field "Skills:" "$skill_note"
    field "Skill path:" "$skill_destination"
    mkdir -p "$home_dir"

    cat \
        "$ROOT_DIR/core/instructions/AGENTS.md" \
        <(printf '\n\n') \
        "$provider_dir/instructions.md" \
        > "$instruction_path"
    log "Wrote $instruction_path"

    rm -rf "$CANONICAL_SKILLS_DIR"
    mkdir -p "$CANONICAL_SKILLS_DIR"
    copy_core_skills "$CANONICAL_SKILLS_DIR" "$include_llm_wiki"
    log "Copied $shared_skill_count shared skills to $CANONICAL_SKILLS_DIR"
    if [[ "$include_llm_wiki" == "yes" ]]; then
        log "Copied $(skill_count "$ROOT_DIR/core/skills" llm-wiki) llm-wiki skills to $CANONICAL_SKILLS_DIR"
    fi

    if provider_uses_canonical_skills "$provider"; then
        if [[ -d "$skills_dir" ]]; then
            rm -rf "$skills_dir"
            log "Removed provider-local skills mirror at $skills_dir"
        fi
    else
        rm -rf "$skills_dir"
        mkdir -p "$skills_dir"
        cp -R "$CANONICAL_SKILLS_DIR/." "$skills_dir/"
        log "Mirrored skills to $skills_dir"
    fi

    apply_auto_approval_config "$provider"
    log "Applied auto-approval permissions for $provider"

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

ask_include_llm_wiki() {
    local answer

    answer="$(read_answer "Install optional llm-wiki skills? [y/N] " "n")"
    echo >&2
    if is_yes "$answer"; then
        printf "yes"
        return
    fi

    printf "no"
}

run_auto_mode() {
    local detected=()
    local selected=()
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
        local include_llm_wiki
        include_llm_wiki="$(ask_include_llm_wiki)"
        for provider in "${detected[@]}"; do
            install_provider "$provider" "$include_llm_wiki"
        done
        return
    fi

    for provider in "${detected[@]}"; do
        answer="$(read_answer "Install $provider? [y/N] " "n")"
        echo >&2
        if is_yes "$answer"; then
            selected+=("$provider")
        fi
    done

    if [[ ${#selected[@]} -eq 0 ]]; then
        return
    fi

    local include_llm_wiki
    include_llm_wiki="$(ask_include_llm_wiki)"
    for provider in "${selected[@]}"; do
        install_provider "$provider" "$include_llm_wiki"
    done
}

case "$TARGET" in
    codex|claude|gemini|copilot)
        INCLUDE_LLM_WIKI="$(ask_include_llm_wiki)"
        install_provider "$TARGET" "$INCLUDE_LLM_WIKI"
        ;;
    all)
        INCLUDE_LLM_WIKI="$(ask_include_llm_wiki)"
        install_provider codex "$INCLUDE_LLM_WIKI"
        install_provider claude "$INCLUDE_LLM_WIKI"
        install_provider gemini "$INCLUDE_LLM_WIKI"
        install_provider copilot "$INCLUDE_LLM_WIKI"
        ;;
    auto)
        run_auto_mode
        ;;
    *)
        usage
        exit 1
        ;;
esac
