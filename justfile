# Task runner for agent-toolbox. `just` (or `just --list`) shows every recipe.
# AGENTS.md points here instead of re-spelling commands, so this file is the
# single source of truth for *how* the repo is built, checked, and installed.

_default:
    @just --list

# --- Marketplace catalogs -----------------------------------------------------

# Regenerate both marketplace.json catalogs from the plugins/ dirs on disk.
gen:
    uv run python scripts/gen-marketplaces.py

# Fail if the committed catalogs are stale (run in `check` and CI).
drift: gen
    git diff --exit-code .claude-plugin/marketplace.json .agents/plugins/marketplace.json

# --- Quality gate -------------------------------------------------------------

lint:
    uv run ruff check

fmt:
    uv run ruff format

types:
    uv run ty check

test:
    uv run pytest

# Everything CI enforces: catalogs in sync, lint, types, tests.
check: drift lint types test

# --- Maintainer tasks ---------------------------------------------------------

# Install shared instructions, unpackaged skills, and Codex agents into
# provider home dirs (~/.claude, ~/.codex, ~/.gemini, ~/.copilot).
setup:
    ./scripts/install.sh

# Set a plugin's version across its Claude + Codex manifests, e.g. `just bump knack 1.9.0`.
bump plugin version:
    ./scripts/bump-plugin-version.sh {{plugin}} {{version}}

# No `update-plugins` recipe: `claude plugin update` refreshes from the published
# marketplace (not your working tree), and there's no stable Codex equivalent to
# pair it with -- a one-harness recipe would silently do half the job, the exact
# drift this repo's generation + tests exist to prevent. Update via each harness's
# own plugin command until both verbs are settled.
