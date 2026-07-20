---
name: implement
description: "How to implement a spec or feature: prove behavior before committing to it, and orchestrate the work rather than doing it all yourself. Use whenever implementing a feature, bugfix, or behavior change."
---

# Implement

One verification discipline and one stance.

## Prove behavior before you commit to it

**`/tdd`** is the discipline (the sketch→graduate→settle loop lives there):
every stated goal ends proven by a committed functional test at caller altitude,
written directly when the behavior is known or graduated from a `tests/temp/`
scratch script when it isn't. A verdict-only script ends in a recorded decision —
an ADR, spec decision, or tracker entry — rather than a test. If you catch
yourself calling a goal done with nothing that verifies it, STOP and write the
check; a red test, type error, or lint failure is a stop, not a warning.

## Working from the tracker

When the work comes from the tracker, take the next unblocked workable issue.
Slices in an approved spec's container are **ready by construction** — work any
unblocked one without interrogating labels; skip only `ready-for-human`. The
`ready-for-agent` label matters when picking up issues from other sources (the
triage vocabulary and tracker selection live in `/to-issues`). The issue body
is the brief; the latest comment is the handoff — read both before acting. If
mid-task you hit a decision only a human can make, comment exactly what's
needed and relabel the issue `ready-for-human`.

## Orchestrate; don't do it all yourself

Unless the change is highly trivial, **don't explore the codebase or write the
code yourself — delegate.** Spend your context coordinating, not reading files
and typing implementation.

- **Explore** with an explorer-tier worker (`/delegate`'s `ext-subagent`, or the
  `Explore` subagent) instead of loading many files into your own context.
- **Generate** with subagents or an external worker (`/delegate`'s
  `ext-subagent`). Give each worker exactly the context it needs — the relevant
  `NNNN-<slug>.md` sections, key paths, and where the task fits — no more.
- **Review** what comes back before trusting it.

**The fan-out loop:** take the next unblocked issue → spawn a **doer** (per
`/delegate`) with the issue, a pointer to the spec, and its own `/goal` →
review the diff → update the tracker → repeat.

**Escalation ladder.** A blocked worker reports up, never out — BLOCKED/
NEEDS_CONTEXT to you, never a prompt to the user. Resolve what the spec, ADRs, or
codebase answer; log the decision on the issue; relaunch. Interrupt the user only
for a scope change, a spec contradiction, a blocking `ready-for-human` slice, or
a destructive/irreversible action.

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

Always tell the worker to follow the verification discipline — prove each
stated goal with a functional test per `/tdd`, run and passing — and to report status
(DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED). Handle each status before
proceeding: address concerns that touch correctness or scope, provide missing
context and re-dispatch, or diagnose a block before retrying.

### After each task

Update the tracker issue: move it to Done, or comment progress (what's done,
what's next, the one gotcha). Status and tasks live on the tracker, not in a
local file.

## Cross-references

- `/sharpen` — stress-test a plan before writing tests or scratch scripts.
- `/write-spec new <name>` — scaffold a pure-markdown spec whose Verification section names the tests.
- `/delegate` — the mechanics of exploring and generating via workers.
