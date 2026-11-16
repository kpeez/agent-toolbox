---
name: principle-encode-the-procedure
description: "When you do a project procedure a second time, or the user corrects how you did it, make or update a project skill so the next run starts from it."
disable-model-invocation: true
---

# Encode the procedure

- **Name the procedure in the project's terms.** Use the words the project
  uses, such as `fmri-glm-stats` or `retrieval-eval`. State its inputs,
  its outputs, and the decisions inside it.
- **Choose the smallest home.** A new procedure skill is for a new procedure.
  An update to an existing procedure skill is for a change to that procedure.
  A line in the `research-context` skill is for a fact about the data or a
  convention that many procedures share.
- **Take the real commands from this session.** Copy the commands that ran
  and worked. Do not rebuild them from memory.
- **Turn each correction into a check that runs.** A user correction is a
  validity check. Write it as a command or a script with a pass or fail
  result, not as advice in prose.
- **Keep one procedure per skill.** Split a skill that holds two procedures.
- **A subagent proposes; its lead writes.** A subagent sends the proposed
  change to its lead. It does not write the skill.

Write the skill with [research-skill](../research-skill/SKILL.md).

You skipped this when the user gave the same instruction twice, when you
reconstructed a command that ran earlier in the session, when a correction was
applied but no skill or check records it, or when a skill holds two
procedures.
