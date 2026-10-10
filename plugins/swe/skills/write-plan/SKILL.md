---
name: write-plan
description: "Turn rough notes into a short plan for large or ambiguous work and hand it to a fresh session."
disable-model-invocation: true
---

# Write a plan

Most work needs no plan file: use plan mode or proceed directly. Write one only
when the user asks, or when the work is large or ambiguous, will span
sessions, or will be handed to another agent or provider.

A plan is a handoff, not a record. After the pull request merges, the PR and
the code are the record, and the plan file can be deleted. A decision worth
keeping beyond the PR becomes an ADR when it meets
[the decision-record criteria](../../references/ADR-FORMAT.md).

## Where the plan lives

Use [plan storage](references/plan-storage.md) to locate the shared plans
directory and choose the appropriate sync path. Never write a plan into
`.agents/docs/` or a notes vault.

- `ABC-123-short-slug.md`: eligible to mirror to a document on Linear issue
  ABC-123 through a configured host Stop hook or explicit sync. Confirm the
  recorded sync state before reporting delivery.
- `short-slug.md`: local only, including plans linked to GitHub issues.

When the user wants the work tracked and no issue exists, create one issue for
the plan on the tracker chosen as in [`/to-issues`](../to-issues/SKILL.md)
(title: the goal; body: the outcome in a sentence or two). Use a Linear key in
the filename for an eligible mirror; keep a GitHub-linked plan unkeyed and link
it from the issue. One issue per plan is the default; use `/to-issues` only
when the work needs several pull requests.

## Process

1. Start from the user's notes. Read enough code to use accurate names and
   paths; answer questions by reading the code rather than asking.
2. Ask only the questions whose answers would change the goal, scope, design,
   or verification: one at a time, or a small batch of independent ones. Use
   `/grill` when the design needs a deeper stress test.
3. Write the plan from the template below. Include what the executing session
   needs and cannot read from the code; leave out what it can.
4. Iterate until the user approves it. Approval lives in the conversation; the
   file has no status or approval fields.
5. Hand off. Suggest a fresh session with "Implement the plan in `<path>`",
   which uses `/implement`.

## Template

```markdown
# <Title>

## Goal
<The outcome and why it matters, in one to three sentences.>

## Non-goals
- <Adjacent work that is out of scope.>

## Approach
<Files, interfaces, and the design choices the work depends on. Name paths.>

## Decisions
- <Choice: reason. Include rejected alternatives worth remembering.>

## Verification
- <Observable claim: how it will be checked (test, command, or demonstration).>
```

The file has no frontmatter, identifiers, or status fields.
