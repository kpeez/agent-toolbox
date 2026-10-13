# Skill mechanics

The skill-specific branch of [`writing-for-agents`](SKILL.md): what changes when the document is a skill (frontmatter, the invocation choice, and router skills). Everything else about writing it is the universal reference in `SKILL.md`.

## Invocation

Three modes trade the two loads. Each mode sets who can start the skill and which path loads it.

- A **model-invoked** skill has no invocation flag and a model-facing `description` with its trigger branches (the pointer rules in `SKILL.md` apply in full). The model listing shows it, so the agent can start it, and other skills load it through the Skill tool. The human can also type its name. The description is permanent context load, paid for discoverability.
- A **model-only** skill sets `user-invocable: false`. The model listing shows its description, and the Skill tool loads it, but the slash menu omits it and the host rejects its typed name before any model turn. It pays the same context load as a model-invoked skill and adds no menu entry for the human to remember.
- A **user-invoked** skill sets `disable-model-invocation: true`. The slash menu shows it, the model listing does not, and only the human typing its name starts it. Its `description` is a human-facing one-line summary with no trigger list. Zero context load; the human is the index that remembers it. A Skill-tool call on it fails with an error that tells the agent to ask the user and not to replicate the skill's workflow by other means. So another skill names it for the human and does not route to it through the Skill tool. A router may instead read its `SKILL.md` by path under the human's authority: see [Router skills](#router-skills).

Codex reads `agents/openai.yaml` in the skill folder and ignores `disable-model-invocation`. Its `policy.allow_implicit_invocation` is the switch: `false` removes the skill from the model listing, which gives the user-invoked mode. With no file, the model listing shows the skill, which serves both the model-invoked and the model-only mode; `true` is the documented default and was not probed. So a user-invoked skill sets both `disable-model-invocation: true` and `allow_implicit_invocation: false`. Codex has no observed switch that hides a skill from the human.

Pick a mode by who must start the skill. The human only: user-invoked. The agent or another skill, never the human: model-only. Both: model-invoked.

Reference that several skills need goes in one model-only or model-invoked skill that each loads through the Skill tool, or in a plain file outside the skill system that any skill points at.

## Splitting by invocation

The invocation cut of splitting (the sequence cut lives in `SKILL.md`): split off a model-invoked skill when you have a distinct leading word that should trigger it on its own (a trigger word you actually use in your prompts); split off a model-only skill when another skill must reach it and the human never types it. You pay context load for the new always-loaded description, so that independent reach has to be worth it.

## Router skills

When user-invoked skills multiply past what you can remember, a **router skill** cures that cognitive load: one user-invoked skill that matches the task to a playbook, so the human remembers one name instead of many. A router:

- loads model-invoked and model-only skills through the Skill tool;
- reads its playbook files by an absolute path built from the "Base directory for this skill" line at the top of its loaded body, because the Read tool resolves a relative path against the session's working directory, not the skill folder;
- reads a user-invoked skill's `SKILL.md` by the same kind of absolute path only when the human's invocation of the router carries the authority that skill requires, for example a publish step under a request that authorizes publication; otherwise it names the skill for the human to type;
- copies the playbook's steps into the host task list when one exists, and ends its final reply with every step's state. Headless Claude Code has no task-list tool, and in observed runs the model did not write a text list before its tool calls, so the final state list is the record that always exists.
