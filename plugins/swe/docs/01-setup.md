# Set up swe

This page shows you how to install the `swe` plugin in Claude Code or Codex, make every session use the router, and run your first task. Setup is two commands and, in Codex, a few lines in `AGENTS.md`.

## Install the plugin

In Claude Code, run:

```text
/plugin marketplace add kpeez/agent-toolbox
/plugin install swe@agent-toolbox
```

In Codex CLI, run:

```text
codex plugin marketplace add kpeez/agent-toolbox
codex plugin add swe@agent-toolbox
```

Start a new session after you install. The plugin needs no setup step, no config file, and no generated `AGENTS.md`.

To update, run `claude plugin marketplace update agent-toolbox`, then `claude plugin update swe@agent-toolbox`. In Codex, run `codex plugin marketplace upgrade agent-toolbox`, then `codex plugin add swe@agent-toolbox` again.

## Install the skills only

For an agent without plugin support, or to skip the plugin, install the swe skills with [`npx skills`](https://github.com/vercel-labs/skills):

```text
npx skills@latest add https://github.com/kpeez/agent-toolbox/tree/main/plugins/swe
```

This installs the swe skills and no other plugin. Install all of them, because the router and the playbooks read the other skills by path. Add `-g` to install for your user instead of the current project. Run `npx skills update` to update.

The skills-only install has no hooks and no agents. To make the agent start the router, add the lines in [Add the router rule to AGENTS.md](#add-the-router-rule-to-agentsmd-codex) to `AGENTS.md` or `CLAUDE.md`. Delegated work uses the host's own subagents instead of `daedalus` and `comment-sicko`. The rest of this guide assumes the full plugin.

## Let the hook start the router (Claude Code)

The plugin adds a SessionStart hook. At the start of every session, it puts a short rule from [session-start.md](../hooks/session-start.md) into the context. The rule tells the agent to run `swe:go-deeper` on any new task, then to load `swe:swe-mode` before it acts on a new software task, however small.

So you do not have to type `/swe:swe-mode` each time. The agent starts the router itself, also after a short prompt such as "continue". The rule does not apply to chat, quick factual answers, and work that is not software.

The plugin also adds a PostCompact hook that saves a session summary to the branch's handoff file. [Run long work](07-long-runs.md) covers it.

## Add the router rule to AGENTS.md (Codex)

Codex plugins have no hooks. To get the same behavior, copy the hook's lines into the repository's `AGENTS.md`, or into your user-level `AGENTS.md`:

```text
swe: Before you act on a new task of any kind, run `swe:go-deeper` on it, unless it is chat, a quick factual answer, a fully specified mechanical edit, or go-deeper already ran for it. Before you act on a new software task, load the `swe:swe-mode` skill and follow the playbook or skill it routes to. A software task is any request to change, fix, refactor, speed up, explain, or review code, or to edit a skill, however small it looks. Say `Playbook: <slug>` or `Route: <skill>`, track each step, and end with its Steps section. Skip this only for chat, quick factual answers, and work that is not software. Write replies to the user and agent-facing text in ASD-STE100 Simplified Technical English (the `writing` skill).
```

Without these lines, type `$swe:swe-mode <task>` to start the router in Codex.

## Know where the tokens go

swe spends extra tokens on subagents. Code goes to delegates, reviews go to a fresh reviewer, and `how` and `why` can fan out to several explorers. That is the price of independent checks.

The router picks a model for each job. You do not configure it. In Claude Code, the [router's Subagents section](../skills/swe-mode/SKILL.md#subagents) uses these models:

| Job | Model |
| --- | --- |
| Judgment, prose, and the hardest code | `opus` |
| Routine code | `sonnet` |
| Mechanical edits | `haiku` |

In Codex, the router raises or lowers reasoning effort the same way. The `daedalus` code agent runs on `sonnet` with medium effort in Claude Code. Its Codex definition, [daedalus.toml](../agents/daedalus.toml), pins its own model with maximum reasoning effort.

To spend fewer tokens:

- Ask a narrow question. `how` spawns no explorers for a single module or function.
- Give the router a scoped task with a clear done check, so it does not plan work you did not ask for.
- Run the main chat on a cheaper model. The subagent choices above stay the same.

## Run your first task

Pick something real but small, and describe it the way you would describe it to a colleague:

```text
/swe:swe-mode add a --json flag to the export command. text output stays byte-identical. verify both.
```

The router first names its choice, for example `Playbook: build-feature. Reason: new behavior.` Then it copies each step of that playbook into the task list, such as `1-map-subsystem` and `8-verify-on-surface`. Before each step, it loads the skills and principles that the step names.

The final reply ends with a Steps section. It gives every step with its state. A step the router did not do stays in the list as `skip:` with its reason, so you can see what it chose not to do:

```text
1-map-subsystem: done
9-check-blast-radius skip: the change keeps the public signature
```

A request to build, change, or fix something lets the agent commit, push, open a draft PR, and merge once the work is verified and checks pass. Say "local only" or name a hold point to stop it earlier. A question, a review, or an investigation does not publish: the agent verifies, leaves the work local, and reports. It always pauses before an irreversible write, such as a force-push to a shared branch or a deploy. See [`ship-pr`](../skills/ship-pr/SKILL.md#publication-authority).

If you do not know which skill fits, ask [`/swe:help`](../skills/help/SKILL.md). It answers with a prompt you can send and a link to the file that holds the answer.

Next: [Route work through `/swe:swe-mode`](02-route-work.md).
