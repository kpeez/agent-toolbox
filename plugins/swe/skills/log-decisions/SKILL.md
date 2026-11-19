---
name: log-decisions
description: "Keep an append-only log of each decision in a long, multi-phase, or unattended run, so a reviewer can audit the work later. Use when the user asks for a decision log, or before such a run starts."
---

# Log decisions

A decision log records each fork, unit result, pivot, and blocker of one piece
of work, with evidence a reviewer can open. You append the rows yourself as
the run proceeds. The log lives at
`.agents/scratch/<branch-slug>/decisions.jsonl`, where `<branch-slug>` is the
branch name with `/` changed to `-`.
[Agent scratch](../../references/agent-scratch.md) defines the folder and how
to create its link. Keep one log per piece of work. No script writes the log.

Keep a log for an unattended or autonomous run, a multi-phase run, work a
person reviews after stepping away, or when the user asks. Skip it for short,
attended work: the transcript and the diff are enough.

Other skills and playbooks that need an audit trail use this log. They name
this skill and let it own the format. They do not restate the fields.

## Write a row

Append one JSON line to the log file. Each row holds four fields:

```json
{"ts": "2026-05-24T12:30:00+00:00", "step": "widget", "decision": "threw out a helper's work because its screenshots were blank", "reason": "checked the real files instead of trusting its summary"}
```

- **ts**: the current time in ISO 8601 with the UTC offset. Read the clock
  with `date` when you append.
- **step**: the phase, workstream, or playbook step the decision belongs to.
  Use `start` only for a run's first row, as "Runs and start rows" says.
- **decision**: what was chosen or done, one line. Name the evidence in the
  line: a commit SHA, a PR, `file:line`, or an artifact, trace, or screenshot
  path. Never a paragraph. Prefer output of a committed script over a
  one-off, per
  [encode-lessons-in-structure](../principle-encode-lessons-in-structure/SKILL.md).
- **reason**: the reason in plain words, per the
  [prose rules](../writing/references/prose.md). When a principle drove the
  decision, say what it made you do, not its name as a tag.

Write each row the way you would tell a teammate what you did: plain words
and concrete actions. A reviewer reads this row at a glance.

Write a row at decision points and checkpoints: a fork chosen, a unit done
with its check result, a pivot or revert with its trigger, a blocker found, a
gate fixed. In a loop run, write one row per iteration. Skip routine and
self-evident actions.

The log is append-only. To correct a row, append a row that supersedes it.
Never edit or delete a row.

## Runs and start rows

A run is one agent conversation, including its later turns and any summary of
it. A pickup, a replacement agent, or a new chat starts a new run.

- When a run adds to a log that already has rows, its first row has step
  `start`. So does its first row after another run's `start` row.
- When a run comes back to the log in a later turn, it first reads the last
  rows to see whether another run wrote since.
- A `start` row names, in `decision`, the `ts` range of the earlier rows this
  run did not write, and names this run, such as its session id.

## Before you hand back

1. Read this run's rows: `jq -c . <log>`. This run's stretch starts at its
   `start` row, or at the first row if this run created the log, and ends at
   the next `start` row of another run.
2. Read this run's transcript and walk the rows against what happened. In
   Claude Code it is a `.jsonl` file under
   `~/.claude/projects/<project-slug>/`. In Codex it is under
   `~/.codex/sessions/`. Read only this project's transcript, never other
   projects' sessions.
3. Check that every row maps to a real decision or action, and that each
   evidence pointer in it exists and shows what the row claims.
4. A fork, pivot, or abandoned approach that shaped the work but has no row
   is a gap. Append a row for it.
5. Correct the log, not the story. For a wrong row, even an invented one,
   append a row that supersedes it with what happened and a pointer that
   resolves. Rows outside this run's stretch are not audited; supersede one
   only when this run's own work shows it is wrong.

Done when every row of this run has evidence that resolves and every fork has
a row.

## Review the trail with another model

Before you hand back, start a reviewer subagent on a different model from the
one that did the work: another Claude model in Claude Code, or a model on
another agent CLI through [external-agents](../external-agents/SKILL.md) when
the user asked for it.
Your own review does not replace it.
The reviewer reads the log and the run's transcript and flags what the user
should look at. It does not redo the work. It looks for:

- decisions with weak or absent evidence;
- checks skipped, or claimed without proof in the transcript;
- choices that look risky in hindsight, such as premature work, scope creep,
  or a fix for a symptom;
- gaps the user would miss on a quick read.

Every reply for a run with a log ends with an "Attention" section. Its first
line is `reviewed by <model>`. Then list each flag with the rows or moments it
points to. "No flags" is a valid list. The model line is required.

## At handoff

The [handoff](../handoff/SKILL.md) skill posts the log's key rows to the
work's tracker issue as one comment, then deletes the file. The comment holds
the trail after the scratch folder is gone. When a reviewer needs the trail
to trust the result before the handoff, copy the rows into the pull request
first.
