---
name: handoff
description: "Write the current state of the work to its tracker issue so a new session can continue it. Use when the user asks for a handoff, or before a session ends with work left to do."
---

# Write a handoff

A handoff writes the current state of one piece of work to its tracker issue.
A new session reads the issue and continues. The issue is the record: it
outlives the session, the worktree, and the host. Write no handoff file.

## 1-find-the-record

Find the work's issue in the project's tracker. The issue key in the branch
name, the pull request's linked issue, or the session's brief names it. Read
the issue and its comments first. Then find the work's decision log at
`.agents/scratch/<branch-slug>/decisions.jsonl`, where `<branch-slug>` is the
branch name with `/` changed to `-`.
[Agent scratch](../../references/agent-scratch.md) defines the folder and how
to make it.

## 2-update-the-issue

Update the issue with the current state. Cover the state of the work, what
landed, what is next, and the open decisions. Give each decision its reason.

- Write only facts from this session and the issue. Mark a claim that you did
  not check as not verified.
- Name files, commands, branches, and pull requests exactly. Leave out what
  the next session can read from the code or `git log`.
- With no tracker, post the same state as one comment on the pull request:
  `gh pr comment <pr> --body-file <file>`. Keep it out of the pull request
  body, which describes the change as it will merge.
- With neither a tracker nor a pull request, keep the state in your reply.

Apply the [prose rules](../writing/references/prose.md). Show a design or a
code path with [show-me](../writing/references/show-me.md) visuals.

## 3-close-the-log

When a decision log exists, read its rows. Post the key rows to the issue as
one comment: each fork, pivot, and blocker that shaped the work, with its
reason. With no tracker, add the rows to the pull request comment; with
neither, keep them in your reply. Then delete the log file. The comment holds the
trail; the file is scratch. [log-decisions](../log-decisions/SKILL.md) owns
the row format.

## 4-seed-the-next-session

Print this prompt for the new session: `Continue <issue key>.` With no issue,
print `Continue the work on <branch>.` The prompt is the handoff's last line.
A new session on any host starts from it: Claude Code, Codex, or another
agent reads the issue and picks up the work.
