# agent-toolbox

`agent-toolbox` provides two portable plugins for AI coding agents:

- **SWE** — skills for sharpening and planning work, implementing and
  reviewing changes, and shipping pull requests.
- **Lab** — source-backed research, reproducible experiment loops, and
  data-visualization guidance.

SWE treats the merged pull request and the code as the record. Large work can
start from a short [plan](plugins/swe/skills/write-plan/SKILL.md) that hands off
to a fresh session, with configured mirroring for Linear-linked plans. Its
[implementation discipline](plugins/swe/skills/implement/SKILL.md) challenges
unnecessary code and simplifies the completed change before final verification.
Sound work can stay unchanged. Publication follows the user's authorization.

Lab keeps source checks and experiment boundaries while scaling research
artifacts and delegation to the question. Neither plugin requires a scheduler
or a separate workflow service.

## Install

### Claude Code

```text
/plugin marketplace add kpeez/agent-toolbox
/plugin install swe@agent-toolbox
/plugin install lab@agent-toolbox
```

### Codex CLI

```text
codex plugin marketplace add kpeez/agent-toolbox
codex plugin add swe@agent-toolbox
codex plugin add lab@agent-toolbox
```

### Optional skills.sh skill-only install

```bash
npx skills@latest add kpeez/agent-toolbox
```

This installs editable skills only. Plugin agents still require a
plugin installation.

### Standalone teaching skill

[`teach`](skills/teach/SKILL.md) is an editable, standalone skill, not part of
SWE or Lab. It retains the teaching workflow and four format templates from
the earlier unpackaged skill, with [upstream attribution](skills/teach/NOTICE).

For a new Codex installation, link `skills/teach` from this checkout into
`~/.agents/skills/teach`. Existing `~/.codex/skills/teach` links to this checkout
also work. Invoke it explicitly with `$teach` in the workspace where you want
to learn. It does not activate implicitly. If it does not appear in the skill
selector after restoring or linking it, start a fresh Codex session.

## Delegation

The implementation skill routes substantial work with independent parts to
`swe:orchestrate`. To make the same decision before skill selection, add this
rule to your user-level `AGENTS.md` (Codex) or `CLAUDE.md` (Claude):

> For substantial work with independently executable parts, use
> `swe:orchestrate` to delegate them. Keep tightly coupled work with one agent.
> Send a single independent review directly to the reviewer.

The plugin does not edit user instructions. Existing sessions may retain prior
instructions; use a fresh session after updating.

## Project documents

ADRs, notes, and research default to `.agents/docs/`. Follow an explicit
project or user override. Create subdirectories as needed; the location may be
a regular directory or symlink, tracked or ignored. No setup step, vault, or
generated `AGENTS.md`/`CLAUDE.md` is required.

## Plans

Plans live in `<main checkout>/.agents/plans/`, shared by all worktrees. The
directory keeps itself out of git with its own `.gitignore`.

A plan named `ABC-123-short-slug.md` can be mirrored one way to a document on
Linear issue ABC-123 by a configured host Stop hook
([`plan_sync.py`](plugins/swe/scripts/plan_sync.py)). It reads a Linear personal
API key from `LINEAR_API_KEY`, or else from `~/.config/swe/linear-api-key`
(mode 0600, honoring `XDG_CONFIG_HOME`), so no shell configuration is needed.
Without a key, or without an issue key in the name, plans stay local and nothing
is blocked. Hook delivery varies by host; confirm sync state when it matters.
GitHub-linked plans remain local unless a separate publication route is configured.

New autoresearch runs keep their program, ledgers, logs, configuration, and
generated figures under `artifacts/autoresearch/<tag>/`. Existing runs retain
their recorded paths. A configured vault receives closeout notes and only the
reference figures those notes embed.

## Layout

- `plugins/swe/` — SWE skills, agents, and the plan-sync hook.
- `plugins/lab/` — Lab skills and their runtime scripts and references.
- `skills/teach/` — standalone teaching workflow and format templates.
- `.claude-plugin/marketplace.json` — Claude marketplace catalog.
- `.agents/plugins/marketplace.json` — Codex marketplace catalog.

## Versioning

Update each plugin's version manually in both manifests, and keep the values
identical:

- `plugins/<plugin>/.claude-plugin/plugin.json`
- `plugins/<plugin>/.codex-plugin/plugin.json`
