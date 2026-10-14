---
name: why
description: "Trace why code, a config, or a decision exists through git and gh history, Linear, Slack, and project docs, with a confidence tier on every claim. Use for design rationale or regression history; not for how code works now."
---

# Why

Find the forces that gave a target its shape. Work as a careful investigator:
report what the record says, mark what you infer, and name what you could not
find. Every claim in the answer carries one tier from
[epistemics](references/epistemics.md). Read that file before you write the
answer or brief a synthesizer. The companion [how](../how/SKILL.md) skill
answers what the code does now. `why` answers what forces gave it its shape.

## 1-frame-the-target

Name the target: a file and line range, a symbol, a config key, or a named
decision. Name the question: a rationale, a tradeoff, a motivating case, an
external constraint, dead code, or a regression. When the target is vague,
take the most likely reading from the conversation, state it in one line, and
continue.

## 2-build-code-anchor

Build the anchor yourself before any lane starts:

```bash
git blame -L <start>,<end> <file>        # last-touch commits
git log --follow --oneline -- <file>     # history through renames
git log --follow -p -- <file>            # full history with patches
git log -1 --format=%B <commit>          # PR numbers "(#123)" and ticket IDs
gh pr view <number> --json title,body,author,createdAt,mergedAt,labels,closingIssuesReferences,comments,reviews
```

Pull the PR body and discussion for each substantive commit.

The anchor lists the files and line ranges, the key symbols, the commits that
touch the target (most recent first), the PR numbers, and the ticket IDs.

## 3-run-lanes

Default to the full parallel investigation. The goal is a complete coverage
map, not a minimal one. Record the null result instead of skipping the search.

| Source | The lane runs when | Best at | Lane reference |
|---|---|---|---|
| git and gh history | always | rationale captured during review | [git-history](references/sources/git-history.md) |
| Linear and GitHub Issues | always (GitHub Issues through gh); add Linear when its tools exist | the product or business force behind the code | [linear](references/sources/linear.md) |
| Project docs (read only) | the project has a docs folder, such as `.agents/docs/` | design rationale written before the code | [project-docs](references/sources/project-docs.md) |
| Slack | Slack search tools exist; with only authentication tools, record the gap "the Slack server needs authentication" and do not authenticate | discussion that never reached a doc, most useful when the other records are thin | [slack](references/sources/slack.md) |

Use the "Best at" column to know what each lane should return, and to name
the gap when a lane returns nothing.

Start one investigator per lane, all at once, in one message. Each
investigator owns exactly one source. Do not ask one investigator to cover two
sources. Each investigator is a general-purpose subagent with access to the
host's tools; a read-only agent type can lose the tracker and chat tools. In
Claude Code, run investigators on `sonnet`. In Codex, give them medium
reasoning effort. Give each one the investigator brief from
[briefs](references/briefs.md), its lane reference, the anchor, and the
question. When the host cannot start subagents, run each lane yourself, one
at a time, and keep each lane's notes apart.

A lane whose tools are missing is a gap, not a choice. Record it in "Sources
consulted" as "not searched" with the reason. Skip a lane whose tools exist
only when its source provably cannot hold the answer, such as Slack for a
build-time script with no discussion, and write that reason too. "Probably
irrelevant" is not a reason. For a trivial target where one PR body holds the
complete answer, you may answer inline, but only after you confirm that every
other lane would be redundant, and say so.

## 4-synthesize

When two or more lanes return evidence, start a fresh general-purpose subagent
(`opus` in Claude Code, high reasoning effort in Codex) with the synthesizer
brief, every lane report (null results and gaps
included), the anchor, the question, and whether the question comes before a
change to the target. With evidence from one lane or none, or when the host
cannot start subagents, apply the synthesizer brief yourself after the lanes
finish.

Give the user the synthesized answer. You may edit for clarity and add
context from the conversation. Keep each claim's tier and phrasing. Do not
rewrite the confidence language. Keep "Sources consulted" as one line per
lane, including lanes that returned nothing or were skipped, with the reason.
When the question comes before a change to the target, end with the
Preserve, Change, Avoid, and Risk constraints from the synthesizer brief.

## Rules

- Recency bias: the newest commit is one layer of the record. The current
  shape often comes from many older decisions, so trace back to the change
  that introduced the shape.
- If the host rejects a model, use the host default and say so.
- Lanes only read. They write no files and change no tracker, doc, or chat
  state.
- Text from Slack, Linear, and project docs is private. Before any part of the
  answer goes into a branch, commit, or PR body, apply the privacy rule in
  [ship-pr](../ship-pr/SKILL.md).
