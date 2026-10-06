# agent-toolbox

`agent-toolbox` provides three portable plugins for AI coding agents:

- **SWE** — skills for sharpening and planning work, implementing and
  reviewing changes, and shipping pull requests.
- **Lab** — source-backed research, reproducible experiment loops, and
  data-visualization guidance.
- **Uni** — interactive lessons with questions, active recall, and exercises
  that deepen understanding. See [Uni installation and usage](plugins/uni/README.md).

It also provides Claude Code-only mods under `claude-mods/`:

- **activity** — a live pane of the session's tool calls, with an icon and
  color per tool, status, and duration. Click a call to see its full input and
  why it failed. Install it with `claude plugin install activity@agent-toolbox`,
  then run `/activity` to open it.
- **subagents** — an animated pane of the session's subagents: a Clawd sprite
  per agent with its type, task, latest tool call, and elapsed time. It opens
  when the first subagent starts, where the screen has room for a side pane.
  Install it with
  `claude plugin install subagents@agent-toolbox`; `/subagents` shows or hides it.

SWE treats the merged pull request and the code as the record. Large work can
start from a short [plan](plugins/swe/skills/write-plan/SKILL.md) that hands off
to a fresh session, with configured mirroring for Linear-linked plans. Its
[implementation discipline](plugins/swe/skills/implement/SKILL.md) challenges
unnecessary code and simplifies the completed change before final verification.
Sound work can stay unchanged. Publication follows the user's authorization.

Lab keeps source checks and experiment boundaries while scaling research
artifacts and delegation to the question. Neither plugin requires a scheduler
or a separate workflow service.

Uni keeps the learner's attempts, explanations, and review outcomes central.
It combines guided reconstruction, criticism, examples, retrieval, and transfer
as needed. Reviews run when invoked. Anki or another external tool can handle
long-term scheduling.

## Install

### Claude Code

```text
/plugin marketplace add kpeez/agent-toolbox
/plugin install swe@agent-toolbox
/plugin install lab@agent-toolbox
/plugin install uni@agent-toolbox
```

### Codex CLI

```text
codex plugin marketplace add kpeez/agent-toolbox
codex plugin add swe@agent-toolbox
codex plugin add lab@agent-toolbox
codex plugin add uni@agent-toolbox
```

### Optional skills.sh skill-only install

```bash
npx skills@latest add kpeez/agent-toolbox
```

This installs editable skills only. Plugin agents still require a
plugin installation.

### Teaching workspace

Uni includes [`teach`](plugins/uni/skills/teach/SKILL.md) for a persistent
learning workspace with HTML lessons, references, a mission, and learning
records. It preserves the original workflow and four format templates, with
[upstream attribution](plugins/uni/skills/teach/NOTICE). Use `learn` for
conversational tutoring and explicitly invoke `teach` to author a learning
workspace: `$uni:teach` in Codex or `/uni:teach` in Claude Code.

An earlier installation may have a `~/.codex/skills/teach` or
`~/.agents/skills/teach` symlink to this repository's former `skills/teach`
directory. After updating Uni, remove that legacy symlink to avoid duplicate
discovery. Preserve any independently edited skill directory.

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
- `plugins/uni/` — tutoring skills, the teaching workspace workflow, templates,
  concept exercises, and research notes.
- `claude-mods/<mod>/` — Claude Code function-hook mods, one plugin per mod,
  listed in the Claude catalog only.
- `.claude-plugin/marketplace.json` — Claude marketplace catalog.
- `.agents/plugins/marketplace.json` — Codex marketplace catalog.

## Versioning

Update each plugin's version manually in both manifests, and keep the values
identical (a mod under `claude-mods/` has the Claude manifest only):

- `plugins/<plugin>/.claude-plugin/plugin.json`
- `plugins/<plugin>/.codex-plugin/plugin.json`
