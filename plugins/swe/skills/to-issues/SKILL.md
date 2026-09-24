---
name: to-issues
description: Turn an approved plan into independently verifiable tasks and dependencies on the selected tracker. Not for drafting specs or executing tasks.
---

# /to-issues

Project document paths below default to `.agents/docs/`; follow an explicit
project or user override.

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
   `.agents/docs/CONTEXT.md` when this work has no established tracker.
3. Prior specs only when their configuration is consistent and still applies.
4. An available Linear connection.
5. GitHub when the repository uses it and public issue publication is
   explicitly intended.
6. Local Markdown sibling issue files otherwise.

Read the applicable route reference before writing:

- [GitHub](references/issue-tracker-github.md)
- [Linear](references/issue-tracker-linear.md)
- [local Markdown](references/issue-tracker-local.md)

An inaccessible configured tracker is a limitation to report, not a reason to
silently select another tracker or declare an empty backlog.

## Authority

Planning and drafting tasks are local work. Publishing them to an external
tracker requires authority in the user's request or approved execution scope.
Do not infer that authority from `approved: true`, a tracker field, or an ADR.
Local Markdown writes still must remain inside the authorized workspace scope.

## Tracked workflow checklist

When the selected route is Linear and project configuration enables this workflow,
build the runtime packet automatically from the approved spec and the current
task judgment. Do not add a parallel manual update command ritual or a second
tracker. This skill's job is approved intent turned into verifiable tasks plus
publication.

1. **Validate** the packet, declared paths, and approval and permission
   evidence, reporting findings.
2. **Preview** the project, spec, context, task, and dependency mapping plus any
   conflicts and imported native mappings for explicit review.
3. **Apply** only under explicit publication authority, producing stable mapping
   identifiers and receipts.
4. **Read back** and compare the recorded state with the preview.

Finish with publication receipts and the execution gate. Starting work or
recording a handoff is a separate phase requiring its own existing record
permission for the published project.

Read the focused references only when the phase needs them: [packet and
mapping](references/workflow-packet.md),
[authorization](references/workflow-authorization.md), and
[operations](references/workflow-operations.md). The
[Linear reference](references/issue-tracker-linear.md) owns Linear routing and
publication.

Reuse recorded mappings; an unavailable or archived recorded project stops
publication rather than creating a duplicate. When the tracker cannot take a
conditional write, append the new approved revision to the content mirror,
preserve human edits, and report the sync conflict. Resolve the runtime entry
point relative to the installed SWE plugin resource, never from the current
working directory or a sibling plugin path; confirm current operations with
`--help`.

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

Reuse the tracker's existing states and labels. When the selected tracker has no
established body or label convention, use the optional
[task format reference](references/task-format.md). Do not introduce its
defaults when the tracker already has a convention.

An approved task can still be held, reassigned, superseded, or blocked later.
Respect current tracker state and human ownership.

## Process

1. Read the full approved input and current project context. Consult relevant
   decision history for rationale and the existing tracker container for task
   boundaries or terms. Verify current constraints at their source; an ADR
   neither overrides approved input nor authorizes changing it.
2. Inspect enough current code or documentation to use accurate terms and paths.
   Delegate a bounded evidence-gathering question when that saves bulk context;
   direct targeted reads are also valid.
3. Draft the smallest task set and dependencies. Reuse existing tasks rather
   than duplicating them.
4. Present the breakdown when the invocation requires a review gate. An
   already-approved execution may return it to the caller without asking for
   approval again, but external publication still needs existing authority.
5. When tracker writes are authorized, publish in dependency order using native
   relationships, following the tracked workflow sequence above when it applies.
   Otherwise return the draft and report the missing authority. Reuse a recorded
   valid container. If a recorded container is missing, stop instead of creating
   a duplicate. When creating the first container, record its stable identifier
   in the spec.
6. Set the spec to `status: active` after executable tasks exist. Keep task
   state only in the tracker.

Tracker updates should record meaningful transitions and concise resume
information. Do not create repetitive journals.
