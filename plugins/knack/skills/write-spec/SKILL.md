---
name: write-spec
description: Create a feature spec — a local design draft plus runnable examples that verify behavior before implementation. Use when starting a new feature, when the task requires design thinking, touches multiple files, or spans sessions.
---

# /write-spec - Feature Spec Management

A spec is a **local, transient design draft plus runnable examples**. It exists to
force design thinking before code and to give the human a review gate. It is NOT a
status ledger: task and status truth live on the issue tracker (see `/to-issues`).
Once the design is settled and sliced into issues, the tracker is authoritative —
the local spec is authoring residue.

## The verification rule

This skill follows the `writing-code` discipline. Read it before implementation:
describe behavior → prove it (a failing test via `/tdd` or a red example via
`/blueprint`) → implement until it passes.

## When to use a spec

Use a spec when any of these are true:

- The task requires design thinking or choosing between approaches
- The change touches multiple files or modules
- The work will span more than one session
- You're unfamiliar with the area of the codebase being modified
- The user explicitly asks for a plan or spec

Skip specs for trivial changes — typo fixes, single-line config changes, log line additions, renames.

## If you're already in plan mode

Don't double-dip. Your approved plan **is** the spec. Write it straight to
`specs/<slug>/SPEC.md` as the goal/scope header, expand the design body below the
`---` divider, and flag the header for the user to confirm. Do not re-derive a
second plan you already made.

## Workflow

1. **Goal**: Write the `SPEC.md` goal/scope header — human intent, scope, success criteria, review gate
2. **Design**: Expand the `SPEC.md` design body — approach, behavior, decisions, verification mapping
3. **Fork — hand off or implement solo.** Once the design is settled:
   - **Hand off (default when work will fan out):** run `/to-issues` to publish the
     spec as a parent issue + sub-issues. Separate agents (fresh chats or
     subagents) then pick up each issue and run its own examples → red → implement
     → green → review → PR loop. The tracker owns status from here.
   - **Solo (single-slice spec, one sitting):** continue here — write executable
     scripts in `examples/`, run them red (they FAIL), implement, run them green
     (they PASS), then `/pr`.

## /write-spec new <name>

Creates a feature spec directory with `SPEC.md` plus `examples/`.

<steps>
<step action="slugify">lowercase name, replace spaces with hyphens -> `<slug>`</step>
<step action="ensure-private">ensure a repo-local `specs` symlink exists that points at the private per-repo directory (skip if already linked); never create `specs` as a real committed directory</step>
<step action="mkdir">`specs/<slug>/` and `specs/<slug>/examples/` (no-op if already present)</step>
<step action="create-root-agents">if `specs/AGENTS.md` is missing, create it from the template in `templates.md`</step>
<step action="create-files">read `templates.md` and write `SPEC.md` to `specs/<slug>/`; never overwrite a `SPEC.md` that already exists — a present goal/scope header is human-authored and authoritative</step>
<step action="populate">if `SPEC.md` already exists, treat its goal/scope header as the human-authored source of truth — do not modify it — and expand the design body (approach, behavior, decisions, risks, verification mapping) below the `---` divider. Otherwise fill the goal/scope header from conversation context (intent, scope, non-goals, success criteria, execution mode); if invoked in or after plan mode, draft it from the approved plan and flag it for the user to confirm. Then expand the design body and choose example script names from the behaviors being verified.</step>
</steps>

## Spec structure

A spec is **`SPEC.md` plus `examples/`** — nothing more. Specs are private working
context and must never be committed. Keep `specs` ignored in git. Prefer a
repo-local `specs` symlink that points to a private per-repo directory, such as
`~/Documents/specs/<repo>`.

```md
specs/
├── AGENTS.md # How agents navigate specs; not a manual index
└── <feature>/
    ├── SPEC.md # Human goal/scope header + agent-expanded design
    └── examples/ # Runnable verification scripts (REQUIRED)
        ├── build_pipeline.py # Prefer behavior-specific names
        └── basic_pipeline_run.py # Use useful filenames, not generic placeholders
```

Durable design decisions do NOT live in the spec — record them in committed
`docs/adr/` (see `grill-me`'s `ADR-FORMAT.md`). The optional domain glossary lives
in committed `CONTEXT.md` at the repo root.

### SPEC.md

One file, two ownership zones split by a `---` divider.

**Goal/scope header (human-owned source of truth).** Keep it short enough to
review. Use `/grill-me` to stress-test it before expanding the design.

- **Goal** — what problem are we solving and why
- **Scope** — what is included
- **Non-goals** — what is explicitly out of scope
- **Success criteria** — observable outcomes that define done
- **Execution mode** — `review-gated` or `autonomous`, plus stop conditions
- **Validation** — commands/examples/tests that prove the goal

**Design body (agent-expanded).** Write this after inspecting the repo and before
examples or implementation.

- **Design** — architecture, key components, patterns used
- **Behavior** — how it works; inputs, outputs, state changes, failure modes
- **Decisions** — non-obvious choices, rationale, alternatives considered
- **Risks** — things that could break or need careful verification
- **Verification** — maps each example script to the behavior it verifies

The default is human-first: write the goal/scope header yourself before running
`/write-spec new`. The skill preserves an existing header and never overwrites it,
then expands the design body. If no `SPEC.md` exists, the agent writes the header
from conversation context — including an approved plan-mode plan — and flags it for
you to confirm.

Use `review-gated` for normal collaboration: the user reviews the design body
before implementation. Use `autonomous` for `/goal`, ralph-loop, or similar
workflows: the agent may proceed after writing the design.

**Durable decisions:** if a decision is durable beyond this feature (architecture,
provider policy, storage model, security posture, major framework choice), record
it in committed `docs/adr/` and link it from the Decisions section — do not bury it
in the spec.

### Status and tasks live on the tracker, not in the spec

There is no `STATUS.md`. The issue tracker is the task ledger and the status
source, because it is the one ledger every agent and your phone can read with no
local convention to learn:

- **`/to-issues`** publishes the goal/scope header as a **parent issue** and the
  vertical slices as **sub-issues** under it — the portable default on Linear and
  GitHub. Escalate to a Linear **project** only for large, multi-milestone specs.
- **Status** is the issue state (Todo / In Progress / Done); **what's blocked** is
  the blocked-by links; **the rollup** (e.g. 3/7 done) is the parent/project view,
  reviewable remotely with zero maintenance.
- **Resume across agents or context limits:** read the tracker container and grab
  the next unblocked issue. Before you run out of context, drop a short progress
  comment on the **active issue** — what's done, what's next, the one gotcha the
  next agent needs. That comment is the handoff, and it lives where the next agent
  (any agent) is already looking.

### Publishing

Use `/to-issues` to break a spec into independently-grabbable tracker issues, then
`/pr` (or `/ship` for a hostile review pass first) to publish branch work. `/pr`
handles atomic commits, push, and draft PR creation.

### Example scripts

Every spec has an `examples/` directory with runnable scripts. These are not unit
tests — they are executable demonstrations that verify the feature works. Rules for
example scripts are defined in the `blueprint` skill. The examples ARE the record:
rerun them to verify current state. For tracker-linked work, paste the run result
into the issue comment.

## Resuming work on an existing spec

When picking up an existing spec:

1. Read the tracker container/issue first — phase is the issue states, blocked is
   the blocked-by links, the latest progress comment is the handoff
2. Read `SPEC.md` for intent and design context
3. Run any existing examples to see current state
4. Pick up the next unblocked issue
5. Comment progress on the active issue before you hit a context limit

For older specs, accept legacy layouts: a separate `STATUS.md`/`PLAN.md`/
`implementation.md` and `examples/RUN_LOG.md`/`handoff.md`. Treat them as read-only
history; do not rename or migrate old specs unless the user asks.

## Issue tracker

Spec work is handed to the tracker via `/to-issues`. The tracker is configured in
repo-root `issue-tracker.md` (default Linear). For Linear-linked work, follow
`/using-linear` for deterministic comments and status transitions.
