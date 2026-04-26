# agentspecs

A portable, spec-driven workflow and skill set for AI coding agents — works across Claude Code, Codex CLI, Gemini CLI, and GitHub Copilot CLI with a single source of truth[^1].

## What's Here

```text
agentspecs/
├── core/
│   ├── instructions/AGENTS.md # Shared install instructions
│   └── skills/                # Shared skills for all providers
├── providers/
│   ├── codex/                 # Codex-specific addenda and skills
│   ├── claude/                # Claude-specific addenda and skills
│   ├── gemini/                # Gemini-specific addenda and skills
│   └── copilot/               # Copilot-specific addenda and skills
└── scripts/setup-agent.sh     # Install one provider or all providers
```

## Setup

Install one provider or all providers:

```bash
./scripts/setup-agent.sh
./scripts/setup-agent.sh auto
./scripts/setup-agent.sh codex
./scripts/setup-agent.sh claude
./scripts/setup-agent.sh gemini
./scripts/setup-agent.sh copilot
./scripts/setup-agent.sh all
```

With no argument, the script auto-detects supported providers, asks whether to
install all detected providers, and if you answer no, asks about each detected
provider individually.

The installer also asks whether to install optional `llm-wiki-*` skills. These
skills are tracked in `core/skills/`, but they are not installed by default.

This installs to:

| CLI         | Instructions                               | Skills |
|-------------|--------------------------------------------|--------|
| Claude Code | shared core instructions + Claude addendum | shared + Claude-only |
| Codex CLI   | shared core instructions + Codex addendum  | shared + Codex-only |
| Gemini CLI  | shared core instructions + Gemini addendum | shared + Gemini-only |
| Copilot CLI | shared core instructions + Copilot addendum | shared + Copilot-only |

Re-run after updating agentspecs.

## Skills

| Skill                 | Purpose                                             |
|-----------------------|-----------------------------------------------------|
| `/spec new <name>`    | Create a new feature spec                           |
| `/cleanup [name]`     | Aggressively simplify new code after implementation |
| `/spec-review [name]` | Draft logical commit plan and draft PR docs         |
| `/handoff`            | Capture session context before ending               |
| `python-code`         | Python conventions (auto-loads when writing Python) |
| `subagent-orchestrator` | Provider-specific delegation and fallback skill (Codex, Claude) |

Skills follow the [agentskills.io specification](https://agentskills.io/specification).

## Workflow

```mermaid
graph LR
  A["/spec new"] --> B["implement"]
  B --> C["/cleanup"]
  C --> D["/spec-review"]
  D --> E["/handoff"]

style A fill:#2d333b,stroke:#768390,color:#adbac7
style B fill:#2d333b,stroke:#768390,color:#adbac7
style C fill:#2d333b,stroke:#768390,color:#adbac7
style D fill:#2d333b,stroke:#768390,color:#adbac7
style E fill:#2d333b,stroke:#768390,color:#adbac7
```

| Phase          | What happens                                                                                      |
|----------------|---------------------------------------------------------------------------------------------------|
| `/spec new`    | Create the feature spec — design doc, implementation ledger, decisions log. Establishes intent.   |
| **implement**  | Write the code. Update `implementation.md` as you go (done/next/context).                         |
| `/cleanup`     | Review the diff and aggressively simplify. Inline, delete, rewrite anything overcomplicated.      |
| `/spec-review` | Group clean changes into logical commits. Generate `commits.md` and `draft-pr.md`.                |
| `/handoff`     | Capture session state — what's done, what's next, critical context for the next agent or session. |

Not every session hits every phase. `/cleanup` and `/spec-review` are most useful before committing final changes. `/handoff` is for any session boundary.

## Specs Setup

Store specs in a cloud-synced location, organized per-repo:

```text
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

```text
specs/<feature>/
├── AGENTS.md           # Spec-specific instructions (read first)
├── CLAUDE.md           # contains @AGENTS.md to point Claude to AGENTS.md
├── design.md           # Technical approach, architecture
├── implementation.md   # Current status, done/next items
├── decisions.md        # Non-obvious choices and rationale
└── future-work.md      # Deferred ideas
```

**`specs/INDEX`** (TSV) provides an at-a-glance overview of all specs:

```text
slug phase blocked desc
user-auth implementing no JWT auth flow
api-v2 design yes:schema pending REST to GraphQL
```

Managed automatically by `/spec new` (adds row) and `/handoff` (updates row).

The core of context continuity is `implementation.md`:

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

---

[^1]: Inspired by this Tweet by Ashpreet Bedi: <https://x.com/ashpreetbedi/status/2011220028453241218>
