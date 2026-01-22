# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

agentspecs is a meta-framework providing standardized conventions and skills for AI coding agents. It contains no application code. Only Markdown specifications that get symlinked into agent config directories.

## Setup

Run the update script to sync to all supported AI CLIs:

```bash
./update_agentspecs.sh
```

## Structure

```text
agentspecs/
├── AGENTS.md                  # Core coding conventions (language-agnostic)
├── update_agentspecs.sh       # Sync to Claude/Codex/Gemini configs
└── skills/
    ├── spec/                  # /spec new, /spec status
    │   ├── SKILL.md
    │   └── scripts/
    ├── handoff/SKILL.md       # /handoff
    └── python/SKILL.md        # Python conventions (auto-loads)
```

## Skills

| Skill              | Purpose                                                                             |
|--------------------|-------------------------------------------------------------------------------------|
| `/spec new <name>` | Create feature spec (AGENTS.md, CLAUDE.md, design.md, ledger.md, decisions.md, future-work.md, optional examples/) |
| `/spec status`     | Show status of all active specs                                                     |
| `/handoff`         | Capture session context for seamless resume                                         |
| `python`           | Python conventions (auto-loads when writing Python)                                 |

## Feature Spec Workflow

For non-trivial features, use `specs/<feature>/` to preserve context across sessions:

1. `/spec new <name>` to create the spec structure
2. Read the spec's `AGENTS.md` before starting work
3. Update `ledger.md` as you work (Done/Next/Context)
4. Log non-obvious decisions in `decisions.md`
5. Verify via examples: run `examples/` and update `TEST_LOG.md`
6. `/handoff` before ending a session

The goal: any new agent reading the spec's `AGENTS.md` and `ledger.md` can continue without re-discovering context.

## When Working Here

- **Editing conventions**: Update AGENTS.md, keep instructions specific and actionable
- **Adding skills**: Create `skills/<skill-name>/SKILL.md` following [agentskills.io/specification](https://agentskills.io/specification)
