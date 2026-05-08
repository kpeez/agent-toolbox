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

Requires Bash and Python 3.

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
All installed skills are written canonically to `~/.agents/skills`. Providers
that do not read that directory natively get copied mirrors in their own home
directories. Provider permission config is merged with existing settings, and
changed provider files are backed up with an `.agentspec-backup-*` suffix.

This installs to:

| CLI         | Instructions                                | Skills               | Auto-approval config |
|-------------|---------------------------------------------|----------------------|------------------|
| Claude Code | shared core instructions + Claude addendum  | `~/.agents/skills` + `~/.claude/skills` mirror | `~/.claude/settings.json` |
| Codex CLI   | shared core instructions + Codex addendum   | `~/.agents/skills` + `~/.codex/skills` mirror | `~/.codex/config.toml` + `~/.codex/rules/` |
| Gemini CLI  | shared core instructions + Gemini addendum  | `~/.agents/skills` + `~/.gemini/skills` mirror | `~/.gemini/settings.json` + `~/.gemini/bin/gemini-auto` + `~/.gemini/policies/` |
| Copilot CLI | shared core instructions + Copilot addendum | `~/.agents/skills` | `~/.copilot/settings.json` + `~/.copilot/bin/copilot-auto` |

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
- Gemini uses `general.defaultApprovalMode = "auto_edit"` for direct `gemini`
  launches. Because yolo mode can only be enabled by command-line flag, setup
  also installs `~/.gemini/bin/gemini-auto`, which runs
  `gemini --approval-mode=yolo` with a native policy file prompting before
  destructive shell prefixes.
- Copilot installs `~/.copilot/bin/copilot-auto`, which launches Copilot with
  native `--allow-all` plus destructive `--deny-tool` rules. GitHub documents
  that deny rules take precedence even when `--allow-all` is set. Setup disables
  Copilot `includeCoAuthoredBy`.

## Skills

| Skill                 | Purpose                                             |
|-----------------------|-----------------------------------------------------|
| `/spec new <name>`    | Create a new feature spec                           |
| `/cleanup [name]`     | Aggressively simplify new code after implementation |
| `/spec-review [name]` | Draft logical commit plan and draft PR docs         |
| `/handoff`            | Capture session context before ending               |
| `python-code`         | Python conventions (auto-loads when writing Python) |

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
