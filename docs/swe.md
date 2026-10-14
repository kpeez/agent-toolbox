# swe

This page is for people who use the `swe` plugin: how to start the router,
which skills it has, and where it keeps files.

## Start the router

```text
/swe:playbook <task>     # Claude Code
$swe:playbook <task>     # Codex
```

The router matches the task to one of seven
[playbooks](../plugins/swe/skills/playbook/playbooks/) or to the one skill
that owns the task. It ends with the state of every step and the reason for
each skipped step. The agent can also start the router itself.

| Playbook | Use for |
| --- | --- |
| `fix-bug` | A reported defect to reproduce, root-cause, and fix |
| `build-feature` | New or changed behavior |
| `refactor-structure` | Change structure, keep behavior |
| `improve-performance` | A measured slowness, against a baseline |
| `investigate-question` | A read-only question with a cited answer |
| `author-skill` | Write or edit a skill, `AGENTS.md`, or `CLAUDE.md` |
| `evaluate-agent-change` | Measure how a skill or prompt change affects agent behavior |

## Skills

Each skill also starts on its own when its task comes up.

| Skill | Use for |
| --- | --- |
| `hash-out` | Settle a plan or design with you, one round of questions at a time |
| `write-plan` | Turn rough notes into a short plan, or split a plan into PR-sized issues |
| `handoff` | Save the work's current state for a new session ([handoffs](handoffs.md)) |
| `implement` | Build an approved feature or fix, then verify it |
| `diagnose` | Find the cause of a bug or a performance regression |
| `testing-code` | Design, gate, and audit tests |
| `codebase-design` | Design a new interface, or propose deeper module boundaries |
| `blast-radius` | Find what a change could break beyond its diff |
| `why` | Trace why code or a decision exists, through history and notes |
| `correct` | Fix the class of a repeated agent mistake |
| `orchestrate` | Split work across subagents, or delegate to another provider |
| `ship-pr` | Commit, push, open a draft PR, and drive it to green |
| `merge-conflicts` | Resolve an active merge, rebase, or cherry-pick (model-only) |
| `verification-skill` | Create or audit the project's skill that runs the real app |
| `writing-docs` | Write a README or a docs page |
| `writing-for-agents` | Write a skill, `AGENTS.md`, or `CLAUDE.md` |
| `wait-what` | Explain the last message again, in simpler words |

Twelve `principle-*` skills are model-only. Other skills load them at the step
they apply to, for example
[principle-fix-root-causes](../plugins/swe/skills/principle-fix-root-causes/SKILL.md).

## Verification skill

The verify steps use the project's own verification skill when one exists. It
launches, drives, and observes the real app, and keeps a feature map. Type
`/verification-skill` (`$swe:verification-skill` in Codex) to create one or to
audit one against the app.

## Delegation

`implement` sends large work with independent parts to `orchestrate`. To make
that choice before a skill is picked, add this rule to your user-level
`CLAUDE.md` (Claude Code) or `AGENTS.md` (Codex):

> For substantial work with independently executable parts, use
> `swe:orchestrate` to delegate them. Keep tightly coupled work with one agent.
> Send a single independent review directly to one fresh subagent.

Start a new session after you add it.

`orchestrate` gives each bounded task to the plugin's one agent, `daedalus`.
It does one task (code, tests, docs, or tracker work) under the caller's brief
and publishes nothing without explicit authority. Its default model is Sonnet;
the caller can pick another per task.

Reviews and searches use the host's own subagents, with the rules in the
[review brief](../plugins/swe/references/review-brief.md). By default a
reviewer fixes small, sure findings and reports each fix. A landing verdict
edits nothing.

## Project files

| Files | Location |
| --- | --- |
| ADRs, notes, research | `.agents/docs/`, unless the project or user names another place. It can be a folder or a symlink, tracked or ignored. |
| Plans and handoffs | `<main checkout>/.agents/plans/<branch>.md`, shared by all worktrees and kept out of git by its own `.gitignore`. See [handoffs](handoffs.md). |

The plugin needs no setup step, vault, or generated `AGENTS.md`.
