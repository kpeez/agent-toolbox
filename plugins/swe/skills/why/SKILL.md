---
name: why
description: "Trace why code, a config, or a decision exists through git and gh history, Linear, Slack, and the llmOS vault, with a confidence tier on every claim. Use for design rationale or regression history; not for how code works now."
---

# Why

Find the forces that gave a target its shape. Work as a careful investigator:
report what the record says, mark what you infer, and name what you could not
find. Every claim in the answer carries one tier from
[epistemics](references/epistemics.md). Read that file before you write the
answer or brief a synthesizer.

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
git log -1 --format=%B <commit>          # PR numbers "(#123)" and ticket IDs
gh pr view <number> --json title,body,author,mergedAt,closingIssuesReferences,comments,reviews
```

The anchor lists the files and line ranges, the key symbols, the commits that
touch the target (most recent first), the PR numbers, and the ticket IDs.
Every lane and the synthesizer get the same anchor.

## 3-run-lanes

| Source | The lane runs when | Lane reference |
|---|---|---|
| git and gh history | always | [git-history](references/sources/git-history.md) |
| Linear and GitHub Issues | Linear tools exist, or the anchor names an issue | [linear](references/sources/linear.md) |
| llmOS vault (read only) | the llmos MCP tools exist | [llmos-vault](references/sources/llmos-vault.md) |
| Slack | Slack search tools exist | [slack](references/sources/slack.md) |

Start one investigator per lane, all at once. Each investigator is a
general-purpose subagent. Give it the investigator brief from
[briefs](references/briefs.md), its lane reference, the anchor, and the
question, with absolute paths. The reviewer agent cannot run an MCP lane: its
tool allowlist drops MCP tools. When the host cannot start subagents, run each
lane yourself, one at a time, and keep each lane's notes apart.

A lane whose tools are missing is a gap, not a choice. Record it in "Sources
consulted" as "not searched" with the reason. Skip a lane whose tools exist
only when its source cannot hold the answer, and write that reason too.

## 4-synthesize

When two or more lanes return evidence, start a fresh general-purpose subagent
with the synthesizer brief, every lane report (null results and gaps
included), the anchor, the question, and whether the question comes before a
change to the target. With evidence from one lane or none, apply the
synthesizer brief yourself.

Give the user the synthesized answer. You may edit for clarity and add
context from the conversation. Keep each claim's tier and phrasing.

## Rules

- Recency bias: the newest commit is one layer of the record. The current
  shape often comes from older decisions, so trace back to the change that
  introduced the shape.
- Lanes only read. They write no files and change no tracker, vault, or chat
  state.
- Text from Slack, Linear, and the vault is private. Before any part of the
  answer goes into a branch, commit, or PR body, apply the privacy rule in
  [ship-pr](../ship-pr/SKILL.md).
