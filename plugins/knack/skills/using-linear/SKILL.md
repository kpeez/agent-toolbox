---
name: using-linear
description: "Use when working on Linear-tracked issues or when Linear issue IDs (e.g., ABC-123) appear in conversation or spec files."
---

# Linear Issue Tracking

Use this reference when a spec is linked to a Linear issue. Linear is the
default tracker (configured in repo-root `issue-tracker.md`; see `/to-issues`).

Linear is a tracker, discussion surface, and handoff signal. It is not a
replacement for repo-local specs. The `SPEC.md` goal/scope header is the
canonical plan the agent follows; the `SPEC.md` design body expands the
implementation; `STATUS.md` (with its run log) tracks progress and verification.

## Source of Truth

For non-trivial Linear-linked work, create or update `SPEC.md`, `STATUS.md`, and
`examples/` before implementation.

If Linear comments, issue text, chat, or PR discussion changes the intended
work, reconcile that change into the spec files:

- Update the `SPEC.md` goal/scope header for goal, scope, non-goals, success
  criteria, execution mode, stop conditions, or validation changes.
- Update the `SPEC.md` design body for implementation approach, behavior,
  decisions, risks, or verification mapping changes.
- Update `STATUS.md` for phase, blockers, next work, linked issues, PRs, shipped
  traceability, and the run log when examples are run.

If the right update is unclear, stop and ask before implementing. Do not let a
Linear issue body, comment, or status silently override the `SPEC.md` header.

## Linking

Record Linear issue IDs in `STATUS.md` frontmatter:

```yaml
issues:
  - ABC-123
prs: []
```

Use `STATUS.md` `Linked Work` for human-readable references:

```md
## Linked Work

- Linear: ABC-123
- PR: #12
```

## Status Gates

When Linear tools are available, update the issue at these gates:

- After drafting `SPEC.md`: comment with the spec path and move
  `Ready for Spec` -> `Spec Review`
- When implementation begins: comment with the spec path, branch/worktree, and
  next verification step; move `Ready for Codex` -> `In Progress`
- When blocked: comment with the exact blocker and needed human input; move
  `In Progress` -> `Blocked`
- When a PR or diff is ready: comment with PR/diff link, verification results,
  and review focus; move `In Progress` -> `In Review`
- After merge/shipment: comment with shipped scope, PR, and commit; move
  `In Review` -> `Done`

If the workspace uses different Linear status names, choose the closest matching
states and keep the same gate semantics.

## Comment Templates

```md
Spec ready for review.

Spec: `specs/<slug>/SPEC.md`
Review focus: <specific decision or scope area>
```

```md
Started work.

Spec: `specs/<slug>/`
Branch/worktree: `<branch-or-worktree>`
Next: <next verification or implementation step>
```

```md
Blocked.

Reason: <exact blocker>
Needed from human: <decision, credential, file, or scope choice>
Current state: <what is already done>
```

```md
Ready for review.

PR/diff: <link>
Spec: `specs/<slug>/`
Verification:

- `<command>`: passed
  Review focus: <specific area>
```

```md
Shipped.

PR: <link>
Commit: `<sha>`
Spec status: updated `STATUS.md` (including its run log)
```

## Fallback

If Linear tools are unavailable, keep updating the spec files normally and
include the intended Linear status/comment update in the final response. Do not
delay spec progress just because the tracker cannot be updated.
