# agent-toolbox

A portable, spec-driven workflow and skill set for AI coding agents — works across Claude Code, Codex CLI, Antigravity CLI, and GitHub Copilot CLI with a single source of truth[^1].

## What's Here

```text
agent-toolbox/
├── .claude-plugin/
│   └── marketplace.json       # Claude marketplace; points at plugins/knack and plugins/lab
├── .agents/plugins/
│   └── marketplace.json       # Codex marketplace; points at plugins/knack and plugins/lab
├── plugins/knack/             # Core plugin: spec-driven workflows, skills, and agent definitions
│   ├── .claude-plugin/        #   Claude plugin manifest
│   ├── .codex-plugin/         #   Codex plugin manifest
│   ├── agents/                #   Agent definitions: Claude .md (via plugin), Codex .toml (via setup script)
│   └── skills/                #   Core skills for all providers
├── plugins/lab/               # Research plugin: autonomous experiments and data-viz guidance
│   ├── .claude-plugin/        #   Claude plugin manifest
│   ├── .codex-plugin/         #   Codex plugin manifest
│   └── skills/                #   Research skills (autoresearch, data-viz)
├── AGENTS.md                  # Shared provider-neutral instructions
└── scripts/setup-agent.sh     # Manual path for non-plugin providers and helper scripts
```

## Installation

### Claude Code (plugin)

Register this repo as a marketplace and install:

```bash
/plugin marketplace add kpeez/agent-toolbox
/plugin install knack@agent-toolbox
/plugin install lab@agent-toolbox
```

> `lab` is optional — install it on research machines where you use `autoresearch` and `data-viz`.

### Codex CLI (plugin)

Register this repo as a marketplace and install:

```bash
codex plugin marketplace add kpeez/agent-toolbox
codex plugin add knack@agent-toolbox
codex plugin add lab@agent-toolbox
```

> The Codex plugin delivers skills only. Codex plugins do not deliver agents, so
> the Codex `.toml` subagents are installed by the manual script below.

### Manual install (Codex agents, Antigravity, Copilot, and helper scripts)

Claude Code installs entirely from its plugin. Codex CLI installs skills from its
plugin but needs the manual script for its subagents. Use the manual script for
Codex agents, for providers that do not have a complete plugin install path here,
and for the shared helper commands used by skills.

```bash
./scripts/setup-agent.sh
```

Skills are written to `~/.agents/skills`. The script overwrites the
agent-toolbox-owned Antigravity and Copilot instruction files and refreshes helper
command symlinks.

This installs to:

| Target          | Installed by manual script                       |
|-----------------|--------------------------------------------------|
| Shared skills   | `~/.agents/skills`                               |
| Helper commands | `~/.agents/bin/local-explore` and `ext-subagent` |
| Codex agents    | `~/.codex/agents/*.toml`                         |
| Antigravity CLI | `~/.gemini/AGENTS.md` + skills symlink           |
| Copilot CLI     | `~/.copilot/copilot-instructions.md`             |

Re-run after updating agent-toolbox.

## Skills

| Skill                 | Plugin | Purpose                                                                                               |
|-----------------------|--------|-------------------------------------------------------------------------------------------------------|
| `agentic-development` | knack  | Agent-Driven Development discipline — examples before implementation, red/green verification          |
| `spec`                | knack  | Create and manage feature specs; `/spec new` scaffolds a feature, `/spec status` regenerates overview |
| `adversarial-review`  | knack  | Clean-context hostile review of the branch diff — challenge approach/design, flag bloat (review-only) |
| `pr`                  | knack  | Group branch diff into atomic commits, push, open a draft PR, write the spec markdown artifact        |
| `ship`                | knack  | Chain `/adversarial-review` then `/pr` in one pass                                                    |
| `handoff`             | knack  | Capture session context before ending for a clean resume                                              |
| `delegating-work`     | knack  | Offload exploration and code generation to local or external worker CLIs                              |
| `grill-me`            | knack  | Interview the user relentlessly to stress-test a plan or design                                       |
| `using-linear`        | knack  | Linear issue tracking integration — status gates, comments, and source-of-truth rules                 |
| `qmd`                 | knack  | Search local markdown knowledge bases (Obsidian vaults, notes, docs) with the `qmd` CLI               |
| `autoresearch`        | lab    | Autonomous experiment loops with defined metrics and private logs                                     |
| `data-viz`            | lab    | Research-backed guidance for designing and critiquing charts, plots, and figures                      |

Skills follow the [agentskills.io specification](https://agentskills.io/specification).

## Workflow

```mermaid
graph LR
  A["/spec new"] --> B["implement"]
  B --> C["/adversarial-review"]
  C --> D["/pr"]
  D --> E["/handoff"]

style A fill:#2d333b,stroke:#768390,color:#adbac7
style B fill:#2d333b,stroke:#768390,color:#adbac7
style C fill:#2d333b,stroke:#768390,color:#adbac7
style D fill:#2d333b,stroke:#768390,color:#adbac7
style E fill:#2d333b,stroke:#768390,color:#adbac7
```

| Phase                 | What happens                                                                                                                                                                             |
|-----------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `/spec new`           | Create the feature spec — PLAN.md, SPEC.md, STATUS.md, and runnable examples. Establishes intent.                                                                                        |
| **implement**         | Write the code. Update `STATUS.md` as you go (done/next/context).                                                                                                                        |
| `/adversarial-review` | Clean-context hostile pass in a fresh reviewer. Challenges the approach/design, then flags bloat, smells, and newly obsolete code. Review-only — returns findings; `/ship` applies them. |
| `/pr`                 | Group the diff into atomic commits, push, open a draft PR if missing, write the spec markdown artifact.                                                                                  |
| `/handoff`            | Capture session state — what's done, what's next, critical context for the next agent or session.                                                                                        |

Not every session hits every phase. `/adversarial-review` is most useful before
`/pr`. Use `/ship` to run adversarial review and `/pr` back-to-back. `/handoff`
is for any session boundary.

## GitHub Workflow

Specs are work programs, not PR containers. A single spec can produce multiple
atomic PRs.

- Prefer atomic PRs that can be reviewed independently.
- Use small, logical commits with imperative, conventional-style subjects.
- Generate PR titles and bodies directly from `PLAN.md`, `SPEC.md`,
  `STATUS.md`, linked issues, and the actual diff.
- Do not create `commits.md` or `draft-pr.md` review artifacts.
- Use squash merge by default unless the user explicitly asks for another merge
  method.
- After a PR merges, update the relevant `STATUS.md` with PR number, merge or
  squash commit SHA, and a short note about what shipped.
- `specs/STATUS.md` is regenerated automatically by the knack plugin hook after
  any write to a file under `specs/`. Local git hooks (post-commit, post-merge)
  serve as a safety net for commits made outside an agent session.

## Specs Setup

Specs are private working context and should never be committed. Store the real
files outside the repo (for example `~/Documents/specs/<repo>/`, cloud-synced
and per-repo), add `specs` to `.gitignore`, and symlink `./specs` back in:

```bash
mkdir -p ~/Documents/specs/<repo>
ln -s ~/Documents/specs/<repo> ./specs
echo specs >> .gitignore
```

If you use a worktree-based setup, you should set up the following post-checkout git hook to automatically symlink the specs directory:

```bash
#!/usr/bin/env bash
# post-checkout: $1=prev HEAD, $2=new HEAD, $3=1 if branch checkout

# only act on branch checkouts (not file restores)
[ "$3" = "1" ] || exit 0

# only act when we're inside a linked worktree, not the main repo
git_dir=$(git rev-parse --git-dir)
[[ "$git_dir" == *"/worktrees/"* ]] || exit 0

ln -sfn ~/Documents/specs/<repo> "$(pwd)/specs"
```

## Feature Specs

Specs live under `specs/` with these files (created by `/spec new`):

```text
specs/
├── AGENTS.md           # How agents navigate specs; not a manual index
└── <feature>/
    ├── PLAN.md         # Human-facing goal, scope, success criteria, execution mode
    ├── SPEC.md         # Agent-expanded design, behavior, decisions, verification
    ├── STATUS.md       # Current status, done/next items, merged work
    └── examples/       # Runnable verification scripts and RUN_LOG.md
```

`PLAN.md` is the user-reviewed contract for the work: goal, scope, non-goals,
success criteria, validation, and whether implementation is review-gated or
autonomous. `SPEC.md` is the agent-expanded implementation design after repo
inspection. It includes the approach, behavior, decision log, risks, and
verification mapping. Use a separate ADR file only for decisions that outlive a
single feature, such as architecture, provider policy, storage model, security
posture, or a major framework choice.

Do not maintain a manual `specs/INDEX`. Each spec is self-describing through
`STATUS.md`; derive overviews by scanning `specs/*/STATUS.md` when needed.
The project-level `specs/STATUS.md` file is generated by `spec_status.py`; do
not edit it by hand.

The core of context continuity is `STATUS.md`:

```markdown
---
description: <one or two sentence description for the project overview>
---

# <Title> - Status

## Status

- **Phase**: plan | spec | examples | implementing | verifying | done
- **Blocked**: no | yes (reason)

## Done

- [x] completed item

## Next

- [ ] next item

## Context

<gotchas, key files>

## Merged Work

- PR #12: Add example feature
  - Commit: `abc123`
  - Shipped: implemented the first atomic slice
```

---

[^1]: Inspired by this Tweet by Ashpreet Bedi: <https://x.com/ashpreetbedi/status/2011220028453241218>
