---
name: implement
description: "How to implement a spec or feature: prove behavior before committing to it, and orchestrate the work rather than doing it all yourself. Use whenever implementing a feature, bugfix, or behavior change."
---

# Implement

Two verification disciplines and one stance.

## Prove behavior before you commit to it

- **`/tdd`** — for behavior that warrants tests. One failing test → minimal code →
  repeat, across vertical (never horizontal) slices. Test through public
  interfaces, not internals.
- **`/blueprint`** — to de-risk an approach: a runnable example that imports the
  real repo, proves a planned implementation, then gets grafted in (or thrown away
  if it only answered a design question).

Describe the behavior → prove it (a failing test or a red blueprint) → implement
until green. If you catch yourself writing implementation with nothing that
verifies it, STOP and write the check first.

On a spec, both live in the spec: tests in the project's suite, blueprint examples
under `specs/<feature>/examples/`. Rerun them to verify; the examples are the
record. Test and example failures are spec failures — fix them before marking done.
"Done" also means lint and type-check pass, not just tests.

## Working from the tracker

When the work comes from the tracker, take the next unblocked issue labeled
`ready-for-agent` (the triage vocabulary and tracker selection live in
`/to-issues`). The issue body is the brief; the latest comment is the handoff —
read both before acting. If mid-task you hit a decision only a human can make,
comment exactly what's needed and relabel the issue `ready-for-human`.

## Orchestrate; don't do it all yourself

Unless the change is highly trivial, **don't explore the codebase or write the
code yourself — delegate.** Spend your context coordinating, not reading files
and typing implementation.

- **Explore** with an explorer-tier worker (`/delegate`'s `ext-subagent`, or the
  `Explore` subagent) instead of loading many files into your own context.
- **Generate** with subagents or an external worker (`/delegate`'s
  `ext-subagent`). Give each worker exactly the context it needs — the relevant
  `SPEC.md` sections, key paths, and where the task fits — no more.
- **Review** what comes back before trusting it.

**The fan-out loop:** take the next unblocked `ready-for-agent` issue → spawn a
**doer** (per `/delegate`) with the issue, a pointer to the spec, and its own
`/goal` → review the diff → update the tracker → repeat.

### Sequential or parallel?

- Tasks share files or have ordering dependencies → **sequential**.
- Tasks are independent (disjoint files, no shared state) → **parallel**.

When uncertain, sequential. Parallel conflicts are harder to recover from than
sequential slowness.

### Model selection

Use the least powerful model sufficient for the task (tiers per `/delegate`):

| Complexity | Signals                                                     | Role     | Claude                | Codex                 |
| ---------- | ----------------------------------------------------------- | -------- | --------------------- | --------------------- |
| Low        | 1–2 files, mechanical change, complete spec                 | explorer | haiku                 | gpt-5.6-luna (medium) |
| Medium     | Multi-file, integration concerns, pattern matching          | doer     | sonnet (or opus, low) | gpt-5.6-luna (xhigh)  |
| High       | Architecture, design judgment, broad codebase understanding | planner  | fable / opus (high)   | gpt-5.6-sol           |

Always tell the worker to follow the verification discipline — write the test or
blueprint first, confirm red, implement, confirm green — and to report status
(DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED). Handle each status before
proceeding: address concerns that touch correctness or scope, provide missing
context and re-dispatch, or diagnose a block before retrying.

### After each task

Update the tracker issue: move it to Done, or comment progress (what's done,
what's next, the one gotcha). Status and tasks live on the tracker, not in a
local file.

## Cross-references

- `/sharpen` — stress-test a plan before writing tests or blueprints.
- `/write-spec new <name>` — scaffold a spec with an examples directory.
- `/delegate` — the mechanics of exploring and generating via workers.
