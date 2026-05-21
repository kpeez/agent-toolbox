# agentspecs

A portable, spec-driven workflow and skill set for AI coding agents — works across Claude Code, Codex CLI, Antigravity CLI, and GitHub Copilot CLI with a single source of truth[^1].

## What's Here

```text
agentspecs/
├── core/
│   ├── AGENTS.md              # Shared instructions for all providers
│   └── skills/                # Shared skills for all providers
├── providers/
│   └── codex/
│       └── agents/            # Explicit Codex subagent definitions
└── scripts/setup-agent.sh     # Install all providers
```

## Setup

Requires Bash.

```bash
./scripts/setup-agent.sh
```

Skills are written to `~/.agents/skills`. Provider permission config is merged
with existing settings, and changed files are backed up with an
`.agentspec-backup-*` suffix.

This installs to:

| CLI             | Instructions                         | Skills             | Auto-approval config                                               |
| --------------- | ------------------------------------ | ------------------ | ------------------------------------------------------------------ |
| Claude Code     | `~/.claude/CLAUDE.md`                | `~/.agents/skills` | `~/.claude/settings.json`                                          |
| Codex CLI       | `~/.codex/AGENTS.md`                 | `~/.agents/skills` | `~/.codex/rules/`                                                  |
| Antigravity CLI | `~/.gemini/AGENTS.md`                | `~/.agents/skills` | none (use Antigravity's native Turbo/Auto/Off setup and deny list) |
| Copilot CLI     | `~/.copilot/copilot-instructions.md` | `~/.agents/skills` | `~/.copilot/settings.json` + `~/.copilot/bin/copilot-auto`         |

Re-run after updating agentspecs.

## Workflow Permissions

All provider installs default to each CLI's native auto-approval mode:

- Run normal implementation, lint, typecheck, test, and documentation work with
  low-friction defaults.
- Keep filesystem access bounded when the provider exposes a native sandbox.
- Deny destructive command families when the provider exposes native deny rules
  that compose with auto approval: `rm`, `rmdir`, `git clean`,
  `git reset --hard`, recursive `chmod`/`chown`, `rsync --delete`, `sudo`,
  `dd`, and disk erase commands.
- Never add agent attribution to commits or PRs: no `Co-authored-by`,
  `Signed-off-by`, `Generated with`, AI tool signatures, or agent entries in
  contributors lists.
- Clean up files or folders created during the current session when they are no
  longer needed. Generated caches created by the current session, such as
  `__pycache__/`, `.pytest_cache/`, and tool cache folders, are routine cleanup.
- Avoid verification commands that create Python bytecode caches unless the
  cache files are the thing being tested. Prefer `PYTHONDONTWRITEBYTECODE=1`
  for ad hoc Python checks.

Provider behavior is configured during setup:

- Codex uses `approval_policy = "on-request"` and
  `sandbox_mode = "workspace-write"`, sets `commit_attribution = ""`, plus a
  compact native `.rules` file that prompts before destructive shell prefixes.
- Claude uses `permissions.defaultMode = "auto"`. Claude auto mode runs without
  prompts while a classifier blocks risky actions such as force pushes,
  production changes, and irreversible destruction of pre-existing files. Setup
  disables Claude commit and PR attribution settings.
- Antigravity CLI (`agy`) ships its own Terminal Command Auto Execution policy
  (Turbo / Auto / Off) configured through the first-run setup wizard and the
  in-app deny list. Agentspec only installs `~/.gemini/AGENTS.md` and shared
  skills; configure the policy through the Antigravity CLI setup wizard.
- Copilot installs `~/.copilot/bin/copilot-auto`, which launches Copilot with
  native `--allow-all` plus destructive `--deny-tool` rules. GitHub documents
  that deny rules take precedence even when `--allow-all` is set. Setup disables
  Copilot `includeCoAuthoredBy`.

## Skills

| Skill                         | Purpose                                                                      |
| ----------------------------- | ---------------------------------------------------------------------------- |
| `/spec new <name>`            | Create a new feature spec                                                    |
| `/spec status`                | Regenerate the project-level specs/STATUS.md overview                        |
| `/adversarial-review [name]`  | Hostile review of the branch diff — kill bloat, smells, newly obsolete code  |
| `/pr [name]`                  | Group branch diff into atomic commits, push, open draft PR, write HTML diff  |
| `/ship [name]`                | Chain `/adversarial-review` then `/pr` in one pass                            |
| `/handoff`                    | Capture session context before ending                                        |
| `python-code`                 | Python conventions (auto-loads when writing Python)                          |

Skills follow the [agentskills.io specification](https://agentskills.io/specification).

## Workflow

```mermaid
graph LR
  A["/spec new"] --> B["implement"]
  B --> C["/adversarial-review"]
  C --> D["/review"]
  D --> E["/pr"]
  E --> F["/handoff"]

style A fill:#2d333b,stroke:#768390,color:#adbac7
style B fill:#2d333b,stroke:#768390,color:#adbac7
style C fill:#2d333b,stroke:#768390,color:#adbac7
style D fill:#2d333b,stroke:#768390,color:#adbac7
style E fill:#2d333b,stroke:#768390,color:#adbac7
style F fill:#2d333b,stroke:#768390,color:#adbac7
```

| Phase                  | What happens                                                                                         |
| ---------------------- | ---------------------------------------------------------------------------------------------------- |
| `/spec new`            | Create the feature spec — PLAN.md, SPEC.md, STATUS.md, and runnable examples. Establishes intent.    |
| **implement**          | Write the code. Update `STATUS.md` as you go (done/next/context).                                    |
| `/adversarial-review`  | Hostile pass on the branch diff. Delete bloat, smells, and code the diff has made obsolete.          |
| `/review`              | Use the provider's native code review flow for bugs, regressions, security, and edge cases.          |
| `/pr`                  | Group the diff into atomic commits, push, open a draft PR if missing, write the spec HTML artifact.  |
| `/handoff`             | Capture session state — what's done, what's next, critical context for the next agent or session.   |

Not every session hits every phase. `/adversarial-review` and native `/review`
are most useful before `/pr`. Use `/ship` to run adversarial review and `/pr`
back-to-back. `/handoff` is for any session boundary.

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
- Regenerate `specs/STATUS.md` after updating per-spec status. Local git hooks
  can do this as a safety net, but remote GitHub PR events do not run local
  hooks.

## Specs Setup

Specs are private working context and should never be committed. Keep the
repo-local `specs` path ignored by git, and store the real files outside the
repository.

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
bash core/skills/spec/scripts/setup-specs-symlink.sh
```

This gives you cloud backup, per-repo isolation, and portability across machines.
The script creates `~/Documents/specs/<repo>/`, ensures `.gitignore` contains
`specs`, and links `./specs` to the private directory. Pass a slug to override
the directory name:

```bash
bash core/skills/spec/scripts/setup-specs-symlink.sh my-web-app
```

## Feature Specs

Specs live under `specs/` with these files (created by `/spec new`):

```text
specs/
├── AGENTS.md           # How agents navigate specs; not a manual index
└── <feature>/
    ├── AGENTS.md       # Spec-specific instructions (read first)
    ├── CLAUDE.md       # contains @AGENTS.md to point Claude to AGENTS.md
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
The project-level `specs/STATUS.md` file is generated by `spec-status.py`; do
not edit it by hand.

The core of context continuity is `STATUS.md`:

```markdown
---
slug: <slug>
title: <Title>
phase: plan
blocked: false
updated: <YYYY-MM-DD>
summary: <one-line summary for lookup>
issues: []
prs: []
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

Generate the project overview with:

```bash
python3 core/skills/spec/scripts/spec-status.py --write
```

Optionally install local refresh hooks:

```bash
bash core/skills/spec/scripts/install-status-hooks.sh
```

The hook installer writes `post-commit`, `post-merge`, and `post-checkout`
hooks. Use `--include-pre-push` if you also want a pre-push refresh. Hooks never
stage or commit generated output.

---

[^1]: Inspired by this Tweet by Ashpreet Bedi: <https://x.com/ashpreetbedi/status/2011220028453241218>
