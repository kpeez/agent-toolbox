---
name: log-decisions
description: "Keep an append-only log of each decision in a long, multi-phase, or unattended run, so a reviewer can audit the work later. Use when the user asks for a decision log, or before such a run starts."
---

# Log decisions

A decision log records each fork, unit result, pivot, and blocker of one piece
of work, with evidence a reviewer can open. It sits beside the work's handoff
file. The handoff holds the current state; the log holds how the work got
there.

Keep a log for an unattended run, a multi-phase run, or when the user asks.
Skip it for short, attended work: the transcript and the diff are enough.

## Write a row

Run this in the target repository. Resolve the script from this skill's
directory, not the current working directory:

```bash
python3 ../../scripts/handoff.py log --session "${CLAUDE_SESSION_ID}" \
  --phase <phase> --decision "<what>" --why "<reason>" \
  --evidence <pointer> [--evidence <pointer> ...] --result "<outcome>"
```

It appends one JSON line to `<main checkout>/.agents/plans/<branch>.decisions.jsonl`
and prints the path. Git ignores the file.

- **phase**: the phase or workstream. A session's first row in an existing
  log has phase `start` and names the session in `decision`.
- **decision**: what was chosen or done, one line.
- **why**: the reason in plain words, per the
  [prose rules](../writing-docs/references/prose-rules.md).
- **evidence**: pointers only: a commit SHA, a PR, `file:line`, or an
  artifact path. Prefer output of a committed script.
- **result**: the outcome, such as `tests pass`, `reverted`, `INCONCLUSIVE`,
  or `open`.

Write a row when a decision is made or a unit is checked: a fork chosen, a
unit done with its check result, a pivot or revert with its trigger, a blocker
found. Skip routine actions.

The log is append-only. To correct a row, append a row that supersedes it.

## Link it

When you write the handoff file, end its Decisions section with the log path.

## Before you hand back

1. Read this session's rows: `jq -c . <log>`.
2. Open each evidence pointer. It must exist and show what the row claims.
3. For a wrong row, or a fork or pivot that shaped the work but has no row,
   append a row with the correct facts.

Done when every row of this session has evidence that resolves.

## After the work

Delete the log with the handoff file when the pull request merges. When a
reviewer needs the trail to trust the result, copy the log into the pull
request first.
