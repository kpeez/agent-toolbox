---
name: interrogate
description: "Multi-model adversarial review. Several reviewers on different models challenge a change from independent angles, and the lead returns one verdict. Use for 'interrogate', 'adversarial review', 'stress test this', or 'find blind spots'."
disable-model-invocation: true
---

# Interrogate

Spawn one reviewer per model to review code changes adversarially. The
adversarial signal comes from model diversity, not assigned personas. The
deliverable is a synthesized verdict. Do not apply changes automatically.

## Step 1, Scope

Identify what to review from context:

- If the user points at specific files or a diff, use that.
- On a feature branch, run `git diff main...HEAD`, or the diff against the
  right base branch, for the full changeset.
- If the user's message refers to recent work, gather the relevant files.

Package the diff or file contents with any surrounding context files the
reviewers need to understand the code.

## Step 2, Intent

Before you spawn reviewers, state the intent in one clear paragraph. Draw it
from the user's message, the commit messages, the PR description if one
exists, and the code. If you are unsure about the intent, ask the user before
you proceed.

## Step 3, Spawn reviewers

Launch all reviewers in a single message, labeled Reviewer A, Reviewer B, and
so on. Each reviewer is a fresh native subagent that did not write the code,
in the verdict-only mode of the
[review brief](../../references/review-brief.md). Parallel reviewers of one
change must not edit.

Each reviewer runs on a different model. The default pair:

| Reviewer | Claude Code | Codex |
|----------|-------------|-------|
| Reviewer A | `opus` | high reasoning effort |
| Reviewer B | `sonnet` | a different model or medium effort |

For stronger diversity, replace or add a reviewer on another model family,
such as Codex, OpenCode, or Copilot. Use the external-provider mode of
[orchestrate](../orchestrate/SKILL.md), which requires that the user named the
provider and authorized it to receive the repository content. If the host
rejects a model, run that reviewer on the host default and say so. Do not
block the review on the model.

Read [the reviewer prompt](references/reviewer-prompt.md) and fill in the same
template for every reviewer with the stated intent, the diff or file contents,
[the rubric](references/rubric.md), and
[the code-quality lens](references/code-quality-review.md).

## Step 4, Synthesize

As results come back, build one picture. Parse every reviewer's findings.
Merge findings that describe the same issue differently, and note which models
raised each one. Findings that two or more models raised independently are the
highest signal. Read a lone model's finding, but weight it accordingly. Note
disagreements. If one model flags something and another explicitly says the
opposite, that is context for the verdict.

## Step 5, Lead judgment

You are the lead reviewer, a pragmatic senior engineer, not a neutral
aggregator. Read [the lead judgment framework](references/lead-judgment.md) in
full. Put every finding in one of four buckets, with the models that raised it
and a one-line rationale.

- **Act on**. Real issues that affect correctness, security, or
  maintainability given the actual goals. They would block a real PR.
- **Consider**. Legitimate, but you are not sure they outweigh the cost of
  addressing them now. Worth the user's attention.
- **Noted**. Technically valid but not actionable. Context-dependent,
  premature optimization, or low impact at this stage.
- **Dismissed**. Wrong, nitpicky, or missing context, with a brief reason.

## Output format

### Intent
> [The stated intent paragraph from Step 2]

### Reviewers
- Reviewer [label]: [model name], [N findings] (one bullet per reviewer)

### Act On
[Each with its description, which models raised it, and why it matters.]

### Consider
[Each with its description, which models raised it, and the tradeoff.]

### Noted
[Brief list.]

### Dismissed
[Each with a brief rationale.]

### Agreement Map
[Where models agreed and diverged, and what that pattern tells us.]
