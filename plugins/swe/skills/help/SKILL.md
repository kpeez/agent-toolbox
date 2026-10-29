---
name: help
description: "Guide the user through swe setup, /swe:swe-mode, and the choice of a skill, playbook, or principle for a task. Type /swe:help with a question."
argument-hint: "[question]"
disable-model-invocation: true
---

# swe help

Answer the user's question about swe, give them a prompt they can send, and
link the file that holds the answer. For a help question, do not start the
work. The user asked how, and a swe run spends real tokens, so let them send
the prompt.

A message that asks for work, such as "use swe to fix this bug", is not a
help question. Read [swe-mode](../swe-mode/SKILL.md) and do the work under it.

This file maps questions to the skills and guide pages that hold the answers.
Those files own the details. Read the file you route to before you quote it,
and trust it when it disagrees with this map. The links here point into the
installed plugin, which the user may not be able to open. Give the user the
public copy: `https://github.com/kpeez/agent-toolbox/blob/main/plugins/swe/`
followed by the file's path in the plugin. Guide pages are in the plugin's
`docs/` folder.

## Find out what they need

Infer the need from the message and the conversation. A named situation, such
as "which skill reviews a PR?", goes straight to its section. If the need is
still unclear, ask one multiple-choice question with these options, then
answer only the section they pick:

- Get set up
- Start a task with `/swe:swe-mode`
- Pick a skill for a situation
- Fix a run that went wrong
- Make swe my own

When the question is about proof that a change works, check the project for a
verification skill. If it has none, mention `verification-skill`.

## Get set up

1. Install the plugin from the agent-toolbox marketplace. Guide page
   `01-setup.md` has the commands for Claude Code and Codex.
2. In Claude Code, the SessionStart hook tells each session to route software
   tasks through `swe:swe-mode`. In Codex, copy the router rule into
   `AGENTS.md`, as page `01-setup.md` shows.
3. Start a real task with `/swe:swe-mode` (`$swe:swe-mode` in Codex), a goal,
   and a check that can pass or fail.

If cost is the worry, say where the tokens go. swe spends extra tokens on
subagents and reviewers. The Subagents section of
[swe-mode](../swe-mode/SKILL.md) matches the model to the job, so routine work
runs on a cheaper model. Page `01-setup.md` has the details. Save
`/swe:swe-mode` for work that needs rigor.

## Start a task with `/swe:swe-mode`

`/swe:swe-mode` matches the task to a playbook or to a single-skill route,
copies the playbook's steps into the task list, and loads the other skills as
the steps need them. A step it skips stays in the list as `skip: <reason>`. A
good prompt states the goal and how to tell it is done. It does not list
skills, because a hand-written order tends to drop or reorder steps that the
playbook keeps. Read [references/prompting.md](references/prompting.md)
before you help word one. Page `02-route-work.md` has examples.

Mid-chat, "new task" makes the router match a fresh playbook. The router
gives code work to the `daedalus` agent, and gives it the router's path so it
reads the same principles.

## Pick a skill

The default answer is `/swe:swe-mode`, which loads most of the others when
its steps need them. Name a skill directly when the user wants more or less
of something than the playbook gives. Read the skill before you recommend it,
and give one example prompt.

| The user wants to | Skill |
|---|---|
| Do any nontrivial software task with rigor | [swe-mode](../swe-mode/SKILL.md) |
| Check that the agent understood the goal before it starts | [in-your-own-words](../in-your-own-words/SKILL.md) |
| Make a task deeper, not bigger, before it starts | [go-deeper](../go-deeper/SKILL.md) |
| Settle open plan or design decisions in an interview | [interview-user](../interview-user/SKILL.md) |
| Know how code works now, or where new code goes | [how](../how/SKILL.md) |
| Know why code is shaped this way | [why](../why/SKILL.md) |
| Catch up on their own recent work on a topic | [recall](../recall/SKILL.md) |
| Catch up on this chat since their last message, with every waiting call decidable from the reply | [ketchup](../ketchup/SKILL.md) |
| Catch up like `ketchup`, in a short subtitled video of slides, with the waiting calls as text under it | [ketchup-video](../ketchup-video/SKILL.md) |
| Hear the last reply again in plain words | [wait-what](../wait-what/SKILL.md) |
| Explain a failure, crash, hang, or leak | [diagnose](../diagnose/SKILL.md) |
| Know what a diff could break outside itself | [blast-radius](../blast-radius/SKILL.md) |
| Settle types and module shape before code that crosses a function boundary | [architect](../architect/SKILL.md) |
| Design a new interface, or review module boundaries | [codebase-design](../codebase-design/SKILL.md) |
| Run parallel checks over slices, or race workers | [swarm](../swarm/SKILL.md) |
| Run a swarm of OpenCode workers | [opencode](../opencode/SKILL.md) |
| Gate, design, or audit tests | [testing-code](../testing-code/SKILL.md) |
| Apply TypeScript rules to `.ts` or `.tsx` work | [typescript-best-practices](../typescript-best-practices/SKILL.md) |
| Strip comments before review | [no-comments](../no-comments/SKILL.md) |
| Write a README, docs page, PR body, or commit message | [writing](../writing/SKILL.md) |
| Write a skill, `AGENTS.md`, or `CLAUDE.md` | [writing-for-agents](../writing-for-agents/SKILL.md) |
| Give agents a scripted way to drive the app | [verification-skill](../verification-skill/SKILL.md) |
| Formally verify a race, invariant, or other property that tests rarely reach | [create-formal-verification-skill](../create-formal-verification-skill/SKILL.md) |
| Bring a formal verification back in line after the code it covers changed, and tell drift from a bug | [maintain-formal-verification-skill](../maintain-formal-verification-skill/SKILL.md) |
| Show a PM or designer what the user sees as a chart checked by a TLA+ model, with the shortest path to each state that breaks a rule | [statechart](../statechart/SKILL.md) |
| Vet a performance number before reporting it | [benchmark-checklist](../benchmark-checklist/SKILL.md) |
| Run a large or cross-cutting change, or one to review after stepping away | [figure-it-out](../figure-it-out/SKILL.md) |
| Keep a decision log during a run | [log-decisions](../log-decisions/SKILL.md) |
| Save the work's state for a new session | [handoff](../handoff/SKILL.md) |
| Open, fix, or land a PR, including its conflicts | [ship-pr](../ship-pr/SKILL.md) |
| Turn what a session taught into skill edits | [reflect](../reflect/SKILL.md) |
| Stop agents from repeating a mistake in this repo | [correct](../correct/SKILL.md) |
| Find their way around swe | `/swe:help` |

If a skill folder next to this one is missing from the table, read its
frontmatter and route by its description. The `principle-*` folders are
covered under principles below.

Close calls:

- `how` explains what the code does. `why` explains the reasons.
- `architect` settles a new design before code. `codebase-design` reviews the
  boundaries of existing code and writes a report.
- A reviewer agent with [references/review-brief.md](../../references/review-brief.md)
  reviews a diff. `blast-radius` looks for breakage outside the diff.
- `recall` rebuilds context across recent chats. `ketchup` covers only this
  chat since the user's last message. To resume one branch, the
  `pick-up-session` playbook applies.
- `figure-it-out` designs one rigorous run. The `run-program` playbook runs a
  program across days and many PRs. The `run-autonomously` playbook drives
  one task to an exit condition.
- `swarm` fans out native subagents. `opencode` runs several one-shot
  OpenCode workers on any model OpenCode can reach, Copilot included.

## Playbooks and principles

Playbooks are step lists inside `/swe:swe-mode`, not skills, so they have no
slash command. Describe the task, and the router picks one. These phrases
name one directly:

- "babysit this pr" or "check on pr 123" runs `babysit-pr`. It drives the PR
  to merge-ready and stops. It does not merge unless the user asks.
- "land the stack" runs `ship-stack`.
- "take over this branch" runs `pick-up-session`.
- "pause safely" runs `pause-safely`.
- "full autopilot on this queue" runs `autopilot-full`. "autopilot, don't
  merge" runs `autopilot-stack`.

The Playbooks section of [swe-mode](../swe-mode/SKILL.md) lists every
playbook and when it applies. Page `06-verify-and-ship.md` covers opening,
babysitting, and landing a PR. For work across phases or stacked PRs, ask
`/swe:swe-mode` for a plan. It runs the `plan-multi-phase` playbook, which
writes the plan and does not implement it.

Principles are one-rule skills that `/swe:swe-mode` reads by path and cites
in its replies. They are hidden from the model listing. The user steers with
the names, as in "apply prove-it-works. show me the real output." Page
`08-principles.md` lists them.

## Fix a run that went wrong

| Symptom | Fix |
|---|---|
| A question got treated as the next step of the last task | Say "new task", or say the turn does not need the router. |
| The router did not start in Codex | Codex has no hook. Add the router rule to `AGENTS.md`, or start each task with `$swe:swe-mode`. |
| Runs cost more than expected | See the cost paragraph under Get set up. |
| A hidden skill did not load on its own | Hidden skills load when the user types them or when `/swe:swe-mode` runs them, and it does not run every skill. |
| Parallel agents overwrote each other | Give each agent its own worktree. |
| A run left alone moved but finished nothing | Give it a check that can pass or fail, not a duration. See page `07-long-runs.md`. |
| The reply claims success from a green build | Ask for the real command, flow, stored value, or profile. That is the prove-it-works principle. |

For a run that drifts, [references/prompting.md](references/prompting.md) has
one-line steers. Page `10-recipes-and-pitfalls.md` has more pitfalls.

## Make swe my own

- `reflect` after a session turns its lessons into skill edits the user
  approves.
- `correct` fixes a repeated mistake at the highest level that works.
- "write a skill for <workflow>" under `/swe:swe-mode` runs the
  `author-skill` playbook. The `evaluate-agent-change` playbook tests a skill
  change blind.
- Fix a broken skill in its own PR, not inside the feature work where it went
  wrong.

Page `09-make-it-yours.md` covers each of these.

## Reply

Lead with the answer. Give at most one example prompt in a code block,
adapted from [references/recipes.md](references/recipes.md) when one fits,
then the link to that file. Keep it short unless the user asked for the whole
map.
