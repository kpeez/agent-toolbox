---
name: spec
description: Create and manage feature specs with Agent-Driven Development (ADD). Specs require runnable example scripts that verify behavior before implementation. Use when starting a new feature, when the task requires design thinking, touches multiple files, or spans sessions.
---

# /spec - Feature Spec Management

## The ADD rule

**Agent-Driven Development: describe behavior, write examples that prove it, then implement until they pass.**

When this skill is active, you MUST:

1. Write spec docs (`PLAN.md` and `SPEC.md`) BEFORE writing source code
2. Write runnable example scripts BEFORE implementation
3. Run examples to confirm they fail (red)
4. Implement the feature
5. Run examples to confirm they pass (green)

If you catch yourself implementing without examples that verify the behavior, STOP. Write the examples first.

## When to use specs

Use a spec when any of these are true:

- The task requires design thinking or choosing between approaches
- The change touches multiple files or modules
- The work will span more than one session
- You're unfamiliar with the area of the codebase being modified
- The user explicitly asks for a plan or spec

Skip specs for trivial changes — typo fixes, single-line config changes, log line additions, renames.

## ADD workflow

1. **Plan**: Write `PLAN.md` — human intent, scope, success criteria, review gate
2. **Specify**: Write `SPEC.md` — agent-expanded implementation design, decisions, verification mapping
3. **Examples**: Write executable scripts in `examples/` that verify expected behavior
4. **Red**: Run examples — they FAIL (feature doesn't exist yet)
5. **Implement**: Write the feature code
6. **Green**: Run examples — they PASS
7. **Update**: Mark `STATUS.md` as done, log results in `RUN_LOG.md`

## Commands

### /spec new <name>

Creates a feature spec directory with standard template files.

<steps>
<step action="slugify">lowercase name, replace spaces with hyphens -> `<slug>`</step>
<step action="check-exists">error if `specs/<slug>/` exists</step>
<step action="mkdir">`specs/<slug>/` and `specs/<slug>/examples/`</step>
<step action="create-files">write all templates below to `specs/<slug>/`</step>
<step action="populate">fill AGENTS.md from conversation context (overview, key files, quick start); fill PLAN.md with user intent, scope, non-goals, success criteria, and execution mode; fill SPEC.md with the implementation approach, behavior, decisions, risks, and verification mapping; choose example script names from the behaviors being verified</step>
<step action="update-index">append row to `specs/INDEX` (create with header `slug\tphase\tblocked\tdesc` if missing)</step>
</steps>

## Spec structure

```
specs/<feature>/
├── AGENTS.md           # Spec-specific agent instructions (read first)
├── CLAUDE.md           # References AGENTS.md for Claude Code auto-discovery
├── PLAN.md             # Human-facing goal, scope, success criteria, execution mode
├── SPEC.md             # Agent-expanded design, behavior, decisions, verification
├── STATUS.md           # Current status and progress
└── examples/           # Runnable verification scripts (REQUIRED)
    ├── build_pipeline.py      # Prefer behavior-specific names
    ├── basic_pipeline_run.py  # Use useful filenames, not generic placeholders
    └── RUN_LOG.md      # Execution log
```

**Index**: `specs/INDEX` (TSV: slug, phase, blocked, desc) — overview of all specs.

### PLAN.md

Human-facing source of truth for the feature. Write this first, either directly
from the user or collaboratively with AI. Keep it short enough to review.

Contents:

- **Goal** — what problem are we solving and why
- **Scope** — what is included
- **Non-goals** — what is explicitly out of scope
- **Success criteria** — observable outcomes that define done
- **Execution mode** — `review-gated` or `autonomous`
- **Stop conditions** — when the agent must stop and ask
- **Validation** — commands/examples/tests that prove the goal

Use `review-gated` for normal collaboration: the user reviews `SPEC.md` before
implementation. Use `autonomous` for `/goal`, ralph-loop, or similar workflows:
the agent may proceed after writing `SPEC.md`, but must keep `STATUS.md`,
examples, and run logs current.

### SPEC.md

Agent-expanded implementation design. Write this after inspecting the repo and
before examples or implementation.

Contents:

- **Problem** — concise restatement of the goal and constraints
- **Approach** — architecture, key components, patterns used
- **Behavior** — how it works; inputs, outputs, state changes, failure modes
- **Decision log** — non-obvious choices, rationale, alternatives considered
- **Risks** — things that could break or need careful verification
- **Verification** — maps each example script to the behavior it verifies

Do not create ADR files by default. Add `ADR-0001-<topic>.md` only when a
decision is durable beyond this feature, such as architecture, provider policy,
storage model, security posture, or major framework choice.

### STATUS.md

Tracks progress. Updated throughout the lifecycle.

```
# <Title> - Status

## Status
- **Phase**: plan | spec | examples | implementing | verifying | done
- **Blocked**: no | yes (reason)

## Done
- [x] completed item

## Next
- [ ] next item

## Context
<gotchas, key files touched, non-obvious things>
```

### Example scripts

Every spec has an `examples/` directory with runnable scripts. These are not unit tests — they are executable demonstrations that verify the feature works.

Rules for example scripts:

- Self-contained and runnable (e.g., `python examples/build_pipeline.py`)
- Exit 0 on success, non-zero on failure
- Print what they're checking and the result
- Written BEFORE implementation (they fail initially)
- Name scripts after the behavior they verify
- Avoid generic names like `basic_usage.py`, `example.py`, or `test.py`
- If a spec has one example, that filename should still describe the workflow or outcome it proves

### examples/RUN_LOG.md

Log results every time you run an example:

```
### <script_name>
**Status:** PASS | FAIL
**Date:** <date>
**Description:** <what this verifies>
**Result:** <observation>
```

Example failures are spec failures — fix them before marking done.

## Templates

<templates dir="specs/<slug>/">

<template file="AGENTS.md">
# <Title> - Agent Instructions
<!-- overview | key files | conventions | quick start -->
Read this file first when working on this feature.
</template>

<template file="CLAUDE.md">
@AGENTS.md
</template>

<template file="PLAN.md">
# <Title> - Plan

## Goal

<!-- what problem are we solving and why -->

## Scope

<!-- what is included -->

## Non-goals

<!-- what is explicitly out of scope -->

## Success Criteria

<!-- observable outcomes that define done -->

## Execution Mode

- **Mode**: review-gated
- **Stop and ask before**: destructive commands, production/shared infrastructure changes, credentials, broad rewrites, or scope changes

## Validation

<!-- commands/examples/tests that prove the goal -->
</template>

<template file="SPEC.md">
# <Title> - Spec

## Problem

<!-- what problem are we solving and why -->

## Approach

<!-- architecture, key components, patterns used -->

## Behavior

<!-- how does it work? inputs? outputs? this maps to example scripts -->

## Decisions

<!-- non-obvious choices: what we chose, why, what alternatives were considered -->

## Risks

<!-- what could break or needs careful verification -->

## Verification

<!-- maps example scripts to behaviors they verify -->
<!-- - `build_pipeline.py` -> proves the pipeline can be assembled -->
<!-- - `basic_pipeline_run.py` -> proves the happy-path execution works -->
</template>

<template file="STATUS.md">
# <Title> - Status

## Status

- **Phase**: plan
- **Blocked**: no

## Done

## Next

- [ ] Write PLAN.md (goal, scope, success criteria, execution mode)
- [ ] Write SPEC.md (approach, behavior, decisions, verification mapping)
- [ ] Write example scripts
- [ ] Run examples (red — confirm they fail)
- [ ] Implement the feature
- [ ] Run examples (green — confirm they pass)

## Context

</template>

<template file="examples/RUN_LOG.md">
# <Title> - Run Log
<!-- format: ### script_name / Status: PASS|FAIL / Date / Description / Result -->
</template>

</templates>

## Resuming work on an existing spec

When picking up an existing spec:

1. Read `specs/<feature>/AGENTS.md` and `STATUS.md`
2. Check the Phase and Blocked status
3. Review `PLAN.md` for intent and `SPEC.md` for implementation context
4. Run any existing examples to see current state
5. Pick up from the Next items in `STATUS.md`
6. Update `STATUS.md` as you work

For older specs, accept `implementation.md` as a legacy status file and
`design.md` as a legacy design file. Do not rename old specs unless the user
asks for a migration.
