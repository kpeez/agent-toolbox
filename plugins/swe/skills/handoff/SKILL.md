---
name: handoff
description: "Write the current state of the work to its handoff file so a new session can continue it. Use when the user asks for a handoff, or before a session ends with work left to do."
---

# Write a handoff

A handoff file holds the current state of one piece of work. A new session
reads it and continues. It is a handoff, not a record: after the pull request
merges, delete the file.

## Find the file

Run `python3 ../../scripts/handoff.py path --session "${CLAUDE_SESSION_ID}"` in
the target repository. Resolve the script from this skill's directory, not the
current working directory. It creates the plans directory and prints the
file's path: `<main checkout>/.agents/plans/<branch>.md`, with `/` in the branch
changed to `-`. On `main`, `master`, or a detached HEAD the name is
`<date>-<session>.md`.

When the file exists, read it first. It can hold a plan from `write-plan` or an
earlier handoff.

## Write the file

Overwrite the file with the current state. Do not append a log. Use these
sections, in this order, and write "None" in an empty section:

```markdown
# <Title of the work>

## Goal
## Done
## Decisions
## Next
## Open questions
## Branch and PR
```

- Keep the Goal and the Decisions of the current file, unless this session
  changed them. Give each decision its reason. When the work has a decision
  log from [log-decisions](../log-decisions/SKILL.md), read its rows first,
  carry each decision that still holds into Decisions, and end Decisions with
  the log path.
- Keep any other section of the current file, such as Non-goals, Approach, or
  Verification from a plan, after Decisions.
- Write only facts from this session and the current file. Mark a claim that
  you did not check as not verified.
- Name files, commands, branches, and pull requests exactly. Leave out what
  the next session can read from the code or `git log`.
- No frontmatter, identifiers, or status fields.
- Apply the [prose rules](../writing-docs/references/prose-rules.md).

Then give the user the path and this prompt for the new session:
`Continue the work in <path>.`

## Compaction

In Claude Code, the swe plugin's PostCompact hook puts each compaction's
summary in the file's `## Session summary` section and keeps the rest. When
you write the file, drop that section: your sections replace it.
