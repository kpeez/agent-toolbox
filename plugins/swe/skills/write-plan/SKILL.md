---
name: write-plan
description: "Turn rough notes into a short handoff plan for large or ambiguous work, or split an approved plan into PR-sized tracker issues. Use when the user asks for a plan or issues, or work will span sessions or go to another agent."
argument-hint: "[notes | issues <plan>]"
---

# Write a plan

This skill has two modes. Pick the mode from the user's arguments or the caller's instruction.

- **Notes** (default): turn rough notes into a plan, as below.
- **`issues <plan>`**: split an approved plan into PR-sized issues: local plan
  files, or issues on Linear or GitHub. Follow [the issues mode](references/issues.md) and skip the rest of
  this file.

Most work needs no plan file: use plan mode or proceed directly. Write one only
when the user asks, or when the work is large or ambiguous, will span
sessions, or will be handed to another agent or provider.

A plan is a handoff, not a record. After the pull request merges, the PR and
the code are the record, and the plan file can be deleted. A decision worth
keeping beyond the PR becomes an ADR when it meets
[the decision-record criteria](../../references/ADR-FORMAT.md).

## Where the plan lives

Use [plan storage](references/plan-storage.md) to locate the shared plans
directory. Name the plan `<slug>.md`, where the slug is the work's branch name
with `/` changed to `-`. The [handoff](../handoff/SKILL.md) skill later updates
the same file. Never write a plan into `.agents/docs/` or a notes vault.

When the user wants the work tracked on a remote tracker and no issue exists,
create one issue for the plan on the tracker chosen as in
[the issues mode](references/issues.md) (title: the goal; body: the outcome in a
sentence or two), and link the plan's path from it. One issue per plan is the
default; use `/write-plan issues` only when the work needs several pull
requests.

## Process

1. Start from the user's notes. Read enough code to use accurate names and
   paths; answer questions by reading the code rather than asking.
2. Ask only the questions whose answers would change the goal, scope, design,
   or verification: one at a time, or a small batch of independent ones. Use
   `/hash-out` when the design needs a full pass over its open decisions.
3. Write the plan from the template below. Include what the executing session
   needs and cannot read from the code; leave out what it can. Apply the
   [unslop](../unslop/SKILL.md) rules.
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
