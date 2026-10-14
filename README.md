# agent-toolbox

`agent-toolbox` provides three portable plugins for AI coding agents:

- **SWE** — an SWE router that runs a task through a step-by-step playbook,
  and skills for hashing out designs and planning work, implementing and
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
- **session-panel** — a control panel for the session. Its tabs show an
  overview with a timeline, each subagent's prompt, trace and answer, each
  shell command with its output, and the files touched. An **ask** button
  attaches a command or an agent run to your next prompt. While subagents run,
  a band above the prompt lists them beside a dancing Clawd for each. Install
  it with `claude plugin install session-panel@agent-toolbox`; `/panel` shows
  or hides it, and `/panel demo` loads sample data.

SWE treats the merged pull request and the code as the record. Large work can
start from a short [plan](plugins/swe/skills/write-plan/SKILL.md) that hands off
to a fresh session, and a [handoff](plugins/swe/skills/handoff/SKILL.md) keeps
its state current between sessions. Its
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

This installs editable skills only. Plugin agents and the SWE router still
require a plugin installation.

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

## SWE router

Type `/swe:playbook <task>` in Claude Code or `$swe:playbook <task>` in
Codex. The agent can also start it. It matches the task to one of seven
[playbooks](plugins/swe/skills/playbook/playbooks/), such as `fix-bug` or
`build-feature`, or to one skill that owns the task. It ends with the state
of every step, including the reason for each skipped step.

The router and its playbooks use these swe skills, which also start on their
own when their moment comes: [why](plugins/swe/skills/why/SKILL.md),
[blast-radius](plugins/swe/skills/blast-radius/SKILL.md),
[correct](plugins/swe/skills/correct/SKILL.md),
[ship-pr](plugins/swe/skills/ship-pr/SKILL.md), and twelve
model-only `principle-*` skills, such as
[principle-fix-root-causes](plugins/swe/skills/principle-fix-root-causes/SKILL.md).

The verify steps use the project's own verification skill when one exists: a
project-local skill that launches, drives, and observes the real app, with a
feature map. Type `/verification-skill` (`$swe:verification-skill` in Codex) to
create one, or to audit an existing one against the app.

## Delegation

The implementation skill routes substantial work with independent parts to
`swe:orchestrate`. To make the same decision before skill selection, add this
rule to your user-level `AGENTS.md` (Codex) or `CLAUDE.md` (Claude):

> For substantial work with independently executable parts, use
> `swe:orchestrate` to delegate them. Keep tightly coupled work with one agent.
> Send a single independent review directly to one fresh subagent.

The plugin does not edit user instructions. Existing sessions may retain prior
instructions; use a fresh session after updating.

`orchestrate` hands bounded work to the plugin's one agent, `daedalus`. It does
one task (code, tests, docs, or tracker work) under the caller's brief, with
the principles the brief names, and publishes nothing without explicit
authority. Its default model is Sonnet; the caller can choose another per
task.

Reviews and searches use the host's native subagents. A review brief
([review-brief](plugins/swe/references/review-brief.md)) carries the review
rules; by default the reviewer fixes small, sure findings and reports each
fix, and a landing verdict edits nothing.

## Project documents

ADRs, notes, and research default to `.agents/docs/`. Follow an explicit
project or user override. Create subdirectories as needed; the location may be
a regular directory or symlink, tracked or ignored. No setup step, vault, or
generated `AGENTS.md`/`CLAUDE.md` is required.

## Plans

Plans live in `<main checkout>/.agents/plans/`, shared by all worktrees. The
directory keeps itself out of git with its own `.gitignore`.

Each piece of work has one file, named after its branch: `write-plan` starts
it, and the `handoff` skill overwrites it with the current state at the end of
a session. In Claude Code, SessionEnd and PreCompact hooks
([`handoff.py`](plugins/swe/scripts/handoff.py)) are the fallback: when a
session edited files in the last hour and after the handoff file last
changed, the hook writes it
with `claude -p --model haiku` from the transcript, in a detached process.
Codex has the skill only. Plans are local; nothing syncs them to a tracker.

New autoresearch runs keep their program, ledgers, logs, configuration, and
generated figures under `artifacts/autoresearch/<tag>/`. Existing runs retain
their recorded paths. A configured vault receives closeout notes and only the
reference figures those notes embed.

## Layout

- `plugins/swe/` — SWE skills, agents, the SWE router and its playbooks,
  and the plan-sync hook.
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

## Credits

- Many `swe` skills, the router and its playbooks among them, adapt Lauren
  Tan's [pstack](https://github.com/cursor/plugins/tree/1dcc2bacde73ddd284803b7af28164d0436198fc/pstack).
- Many `swe` skills, and `uni/skills/teach`, adapt Matt Pocock's
  [skills](https://github.com/mattpocock/skills).
- The `ship-pr` PR-body template's menu of Summary visuals comes from Dex
  Horthy's [`show-me` skill](https://github.com/humanlayer/skills/blob/main/plugins/show-me/skills/show-me/SKILL.md)
  at HumanLayer.
- The audit mode of `swe/skills/testing-code` adapts the OpenClaw
  [test-audit skill](https://github.com/openclaw/openclaw/tree/80930af448ebabc84174146b56bc106d37fab3b4/.agents/skills/test-audit).

Each adapted skill folder has a `NOTICE` with the source and its license.
