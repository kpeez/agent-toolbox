# agentspecs

Agent-agnostic configuration and skills for AI coding agents.

## What's Here

```
agentspecs/
├── AGENTS.md                  # Global instructions for all agents
├── update_agentspecs.sh       # Sync to Claude/Codex/Gemini configs
└── skills/
    ├── spec/                  # /spec new, /spec status
    │   ├── SKILL.md
    │   └── scripts/
    ├── handoff/SKILL.md       # /handoff
    └── python/SKILL.md        # Python conventions (auto-loads)
```

## Setup

Run the update script to sync to all supported AI CLIs:

```bash
./update_agentspecs.sh
```

This installs to:

| CLI | Instructions | Skills |
|-----|-------------|--------|
| Claude Code | `~/.claude/CLAUDE.md` | `~/.claude/skills/` (symlink) |
| Codex CLI | `~/.codex/AGENTS.md` | `~/.codex/skills/` (copy) |
| Gemini CLI | `~/.gemini/GEMINI.md` | `~/.gemini/skills/` (symlink) |

Re-run after updating agentspecs. Codex requires copying (ignores symlinks).

## Skills

| Skill              | Purpose                                             |
|--------------------|-----------------------------------------------------|
| `/spec new <name>` | Create a new feature spec                           |
| `/spec status`     | Show status of all specs                            |
| `/handoff`         | Capture session context before ending               |
| `python`           | Python conventions (auto-loads when writing Python) |

Skills follow the [agentskills.io specification](https://agentskills.io/specification).

## Specs Setup

Store specs in a cloud-synced location, organized per-repo:

```
~/Documents/specs/
├── my-web-app/
│   └── user-auth/
└── another-project/
    └── api-v2/
```

Symlink into each repo:

```bash
mkdir -p ~/Documents/specs/my-web-app
ln -sf ~/Documents/specs/my-web-app ./specs
```

This gives you cloud backup, per-repo isolation, and portability across machines.

## Feature Specs

Each spec lives in `specs/<feature>/` with these files (created by `/spec new`):

```
specs/<feature>/
├── AGENTS.md       # Spec-specific instructions (read first)
├── design.md       # Technical approach, architecture
├── ledger.md       # Current status, done/next items
├── decisions.md    # Non-obvious choices and rationale
└── future-work.md  # Deferred ideas
```

The core of context continuity is `ledger.md`:

```markdown
## Status
- **Phase**: design | implementing | testing | done
- **Blocked**: no | yes (reason)

## Done
- [x] completed item

## Next
- [ ] next item

## Context
<gotchas, key files>
```
