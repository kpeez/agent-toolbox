---
name: to-issues
description: Break an approved plan or spec into independently workable tasks on the selected tracker, with native dependencies and proportionate acceptance evidence.
---

# /to-issues

Turn approved intent into the smallest independently verifiable tasks that
cover the scope. Prefer complete behavioral slices where they help, but do not
force every task through schema, API, UI, and tests. Documentation,
infrastructure, investigation, and focused repairs may have different natural
boundaries.

The spec owns intent and acceptance. The tracker owns executable tasks,
dependencies, assignments, blockers, and progress.

## Select the tracker

Use this evidence in order:

1. The current user's explicit choice, or the current spec's confirmed tracker
   and established container linkage. Do not redirect existing tasks silently.
2. A confirmed repository default in `AGENTS.md`, `CLAUDE.md`, or
   `docs/agents/CONTEXT.md` when this work has no established tracker.
3. Prior specs only when their configuration is consistent and still applies.
4. An available Linear connection.
5. GitHub when the repository uses it and public issue publication is
   explicitly intended.
6. Local Markdown sibling issue files otherwise.

Read the matching reference before writing. An inaccessible configured tracker
is a limitation to report, not a reason to silently select another tracker or
declare an empty backlog.

## Authority

Planning and drafting tasks are local work. Publishing them to an external
tracker requires authority in the user's request or approved execution scope.
Do not infer that authority from `approved: true`, a tracker field, or an ADR.
Local Markdown writes still must remain inside the authorized workspace scope.

## Task design

Each task includes:

- A concrete outcome and why it matters.
- Observable acceptance criteria and proportionate evidence.
- Relevant scope boundaries and useful code or document paths as starting
  points. Paths are guidance; verify them when execution begins.
- Native blocked-by relationships for real dependencies.
- Authority limits and the route for a consequential blocker when needed.

Create one task when one task is enough. Split work when tasks can be owned,
verified, or sequenced independently. Do not add a mandatory changeset layer or
invent grouping that the tracker and review workflow do not need.

Reuse the tracker's existing states and labels. When no convention exists,
these optional triage labels provide a starting point:

| Label | Meaning |
| --- | --- |
| `needs-triage` | Needs evaluation before work |
| `needs-info` | Waiting for information |
| `ready-for-agent` | Fully specified for an agent |
| `ready-for-human` | Needs a human decision or implementation |
| `wontfix` | Will not be actioned |

An approved task can still be held, reassigned, superseded, or blocked later.
Respect current tracker state and human ownership.

## Process

1. Read the full approved input, current project context, applicable ADRs, and
   existing tracker container. Check whether older decisions still apply.
2. Inspect enough current code or documentation to use accurate terms and paths.
   Delegate a bounded evidence-gathering question when that saves bulk context;
   direct targeted reads are also valid.
3. Draft the smallest task set and dependencies. Reuse existing tasks rather
   than duplicating them.
4. Present the breakdown when the invocation requires a review gate. An
   already-approved execution may return it to the caller without asking for
   approval again, but external publication still needs existing authority.
5. When tracker writes are authorized, publish in dependency order using native
   relationships. Otherwise return the draft and report the missing authority.
   Reuse a recorded valid container. If a recorded container is missing, stop
   instead of creating a duplicate. When creating the first container, record
   its stable identifier in the spec.
6. Set the spec to `status: active` after executable tasks exist. Keep task
   state only in the tracker.

Use this issue body as a starting point, adapting it to the tracker:

```md
## Outcome

<The behavior, artifact, or decision this task must produce.>

## Context and starting points

- <Relevant requirement, path, component, or prior decision.>

## Acceptance criteria

- [ ] <Observable, checkable criterion and acceptable evidence.>

## Scope

- In: <owned work>
- Out: <adjacent work>

## Blocked by

- <Native dependency reference, or none>

## Authority and escalation

<External-action limits and consequential blocker route, when applicable.>
```

Tracker updates should record meaningful transitions and concise resume
information. Do not create repetitive journals.
