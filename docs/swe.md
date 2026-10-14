# swe

This page is for people who use the `swe` plugin: how to start the router,
which playbooks and skills it has, and where it keeps files. swe adapts Lauren
Tan's [pstack](https://github.com/cursor/plugins/tree/1e5c90a4b6f249917bd21fe361b3a2a7deb741b8/pstack)
for Claude Code and Codex: its router, playbooks, principles, and most of its
skills.

## Start the router

```text
/swe:playbook <task>     # Claude Code
$swe:playbook <task>     # Codex
```

The router matches the task to one of the
[playbooks](../plugins/swe/skills/playbook/playbooks/) or to the one skill
that owns the task. It copies the steps into the task list, loads each step's
skills and principles when the step starts, and ends with the state of every
step and the reason for each skipped step. When no playbook fits, or the work
is large, `figure-it-out` writes a bespoke playbook in the same format.

In Claude Code, a SessionStart hook puts a short rule in every session:
route each new software task through the router
([session-start.md](../plugins/swe/hooks/session-start.md)). So the agent
starts the router itself, also after a short prompt such as "continue". Codex
plugins have no hooks: copy the same lines into the repository's `AGENTS.md`.

The router also holds rules that apply in every playbook: triggers (for
example, run `how` before a nontrivial change, `writing` on every prose
surface), autonomy (do reversible work, then report; pause before
irreversible writes), subagent and model choice, and how to write the reply.
See [the router](../plugins/swe/skills/playbook/SKILL.md).

## Write a good prompt

Say the goal, not the ceremony. A useful prompt carries up to five things:

- **The goal.** What is wrong, or what you want.
- **The done check.** A check that can pass or fail.
- **The proof you want.** Command output, a video, a stored value, or a
  before-and-after number.
- **What you know.** A symptom, a repro step, a log line, or a link.
- **The constraints.** "repro first", "no code change yet", "zero behavior
  change", or "let me review before you go on".

```text
/swe:playbook the csv export drops its last row since yesterday's deploy. repro first, then fix. done means the 60k-row fixture exports every row. show me the row counts before and after.
```

## Playbooks

A playbook chains several skills in order for one kind of task. A job that one
skill does from start to end stays a skill, so it can start without the router.

| Playbook | Use for |
| --- | --- |
| `fix-bug` | A reported defect to reproduce, root-cause, and fix |
| `improve-performance` | A measured slowness, against a baseline |
| `hillclimb-metric` | Sustained improvement of one metric, keep or revert per attempt |
| `diagnose-runtime` | A live runtime symptom (leak, spin, glitch); diagnosis only |
| `diagnose-trace` | A captured profile, trace, or heap snapshot; diagnosis only |
| `evaluate-agent-change` | Measure how a skill or prompt change affects agent behavior |
| `author-skill` | Write or edit a skill, `AGENTS.md`, or `CLAUDE.md` |
| `build-prototype` | A throwaway sketch that settles a design fork by observation |
| `match-visual-parity` | Pixel-exact UI equivalence against a baseline |
| `refactor-structure` | Change structure, keep behavior |
| `build-feature` | New or changed behavior |
| `investigate-question` | A read-only question with a cited answer |
| `babysit-pr` | Drive a PR or stack to merge-ready |
| `ship-stack` | Verify a green stack, then land the verified run |
| `run-autonomously` | Drive a long task to a checkable exit condition |
| `plan-multi-phase` | Write a plan for work across phases or stacked PRs |
| `autopilot-full` | A queue of independent PRs, run to merged |
| `autopilot-stack` | A queue of changes, delivered as one stack you land |
| `run-program` | A standing multi-day program under one coordinator |
| `pick-up-session` | Resume a prior agent's in-flight work |
| `pause-safely` | Stop in-flight work so a new session can resume it |
| `clean-worktrees` | Reclaim disk from merged or abandoned worktrees |

## Skills

These skills are in the model's skill list. Each one also starts on its own
when its task comes up.

| Skill | Use for |
| --- | --- |
| `interview-user` | Settle a plan or design with you, one round of questions at a time |
| `write-plan` | Turn rough notes into a short plan, or split a plan into PR-sized issues |
| `handoff` | Save the work's current state for a new session ([handoffs](handoffs.md)) |
| `log-decisions` | Keep an append-only decision log for a long or unattended run ([handoffs](handoffs.md#decision-log)) |
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
| `writing` | Write any prose: docs, PR bodies, handoffs, plans, replies |
| `writing-for-agents` | Write a skill, `AGENTS.md`, or `CLAUDE.md` |
| `wait-what` | Explain the last message again, in simpler words |

These skills are hidden from the model's skill list. Playbook steps and router
triggers read them by path. You can type any of them, such as `/swe:how`.

| Skill | Use for |
| --- | --- |
| `how` | Explain how a subsystem works, with explorer and explainer subagents |
| `architect` | Explore competing designs in parallel before code |
| `swarm` | Fan-out shapes: coverage matrices, races, gauntlets, verifier lanes |
| `figure-it-out` | Write a bespoke playbook when none fits |
| `benchmark-checklist` | Vet a measured number before you report it |
| `sharpen` | Restate a vague ask as an expert would approach it |
| `no-comments` | Remove comments that do not explain a non-obvious why |
| `ketchup` | Catch you up after time away |
| `recall` | Rebuild recent context from chat history and the handoff file |
| `reflect` | Review a session for agent mistakes |
| `in-your-own-words` | Restate the user's goals and problem in your own words |
| `typescript-best-practices` | TypeScript type and pattern rules |

Twenty-five `principle-*` skills are also hidden, so they cost no context until
a step needs one. The router lists each with the moment it applies, and reads
it by path at that step, for example
[principle-fix-root-causes](../plugins/swe/skills/principle-fix-root-causes/SKILL.md).

## Verification skill

The verify steps use the project's own verification skill when one exists. It
launches, drives, and observes the real app, and keeps a feature map. Type
`/verification-skill` (`$swe:verification-skill` in Codex) to create one or to
audit one against the app.

## Delegation

The router's Subagents section sets the rules: the chat that runs the
playbook owns it, code goes to delegates, and each new round goes to a fresh
subagent. In Claude Code it picks `opus` for judgment and the hardest code,
`sonnet` for routine code, and `haiku` for mechanical edits. In Codex it sets
reasoning effort the same way.

`implement` sends large work with independent parts to `orchestrate`. To make
that choice before a skill is picked, add this rule to your user-level
`CLAUDE.md` (Claude Code) or `AGENTS.md` (Codex):

> For substantial work with independently executable parts, use
> `swe:orchestrate` to delegate them. Keep tightly coupled work with one agent.
> Send a single independent review directly to one fresh subagent.

Start a new session after you add it.

The plugin has two agents:

- `daedalus` does one bounded task (code, tests, docs, or tracker work) under
  the caller's brief and publishes nothing without explicit authority. Its
  default model is Sonnet; the caller can pick another per task.
- `comment-sicko` reviews a diff for comments to delete, for `no-comments`.

Reviews and searches use the host's own subagents, with the rules in the
[review brief](../plugins/swe/references/review-brief.md). By default a
reviewer fixes small, sure findings and reports each fix. A landing verdict
edits nothing.

## Project files

| Files | Location |
| --- | --- |
| ADRs, notes, research | `.agents/docs/adrs/`, `notes/`, and `research/`, unless the project or user names another place. It can be a folder or a symlink, tracked or ignored. See the [ADR format](../plugins/swe/references/ADR-FORMAT.md). |
| Plans and handoffs | `<main checkout>/.agents/plans/<branch>.md`, with an optional `<branch>.decisions.jsonl` decision log, shared by all worktrees and kept out of git by its own `.gitignore`. See [handoffs](handoffs.md). |

The plugin needs no setup step, vault, or generated `AGENTS.md`.
