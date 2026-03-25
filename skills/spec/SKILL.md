---
name: spec
description: Create and manage feature specs with Agent-Driven Development (ADD). Specs require runnable example scripts that verify behavior before implementation. Use when starting a new feature, when the task requires design thinking, touches multiple files, or spans sessions.
---

# /spec - Feature Spec Management

## The ADD rule

**Agent-Driven Development: describe behavior, write examples that prove it, then implement until they pass.**

When this skill is active, you MUST:
1. Write spec docs (design.md) BEFORE writing source code
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

1. **Describe**: What does this feature do? What are the inputs? What do the outputs look like?
2. **Design**: Write `design.md` — approach, behavior, decisions
3. **Examples**: Write executable scripts in `examples/` that verify expected behavior
4. **Red**: Run examples — they FAIL (feature doesn't exist yet)
5. **Implement**: Write the feature code
6. **Green**: Run examples — they PASS
7. **Update**: Mark `implementation.md` as done, log results in `RUN_LOG.md`

## Commands

### /spec new <name>

Creates a feature spec directory with standard template files.

<steps>
<step action="slugify">lowercase name, replace spaces with hyphens -> `<slug>`</step>
<step action="check-exists">error if `specs/<slug>/` exists</step>
<step action="mkdir">`specs/<slug>/` and `specs/<slug>/examples/`</step>
<step action="create-files">write all templates below to `specs/<slug>/`</step>
<step action="populate">fill AGENTS.md from conversation context (overview, key files, quick start); fill design.md with the planned approach including behavior and verification mapping</step>
<step action="update-index">append row to `specs/INDEX` (create with header `slug\tphase\tblocked\tdesc` if missing)</step>
</steps>

## Spec structure

```
specs/<feature>/
├── AGENTS.md           # Spec-specific agent instructions (read first)
├── CLAUDE.md           # References AGENTS.md for Claude Code auto-discovery
├── design.md           # What, how, behavior, decisions
├── implementation.md   # Current status and progress
└── examples/           # Runnable verification scripts (REQUIRED)
    ├── basic_usage.py  # Self-contained, exits 0 on success
    └── RUN_LOG.md      # Execution log
```

**Index**: `specs/INDEX` (TSV: slug, phase, blocked, desc) — overview of all specs.

### design.md

Source of truth for the feature. Write this during the planning phase, before examples or implementation.

Contents:

- **Problem** — what problem are we solving and why
- **Approach** — architecture, key components, patterns used
- **Behavior** — how does it work? What are the inputs? What do the outputs look like? This section directly maps to example scripts.
- **Decisions** — non-obvious choices made. Why we chose X over Y, what alternatives were considered.
- **Verification** — maps each example script to the behavior it verifies

### implementation.md

Tracks progress. Updated throughout the lifecycle.

```
# <Title> - Implementation

## Status
- **Phase**: design | examples | implementing | verifying | done
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

- Self-contained and runnable (e.g., `python examples/basic_usage.py`)
- Exit 0 on success, non-zero on failure
- Print what they're checking and the result
- Written BEFORE implementation (they fail initially)
- Free-form naming based on what they verify

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

<template file="design.md">
# <Title> - Design

## Problem
<!-- what problem are we solving and why -->

## Approach
<!-- architecture, key components, patterns used -->

## Behavior
<!-- how does it work? inputs? outputs? this maps to example scripts -->

## Decisions
<!-- non-obvious choices: what we chose, why, what alternatives were considered -->

## Verification
<!-- maps example scripts to behaviors they verify -->
<!-- - `basic_usage.py` -> proves X works with standard inputs -->
</template>

<template file="implementation.md">
# <Title> - Implementation

## Status

- **Phase**: design
- **Blocked**: no

## Done

## Next

- [ ] Write design.md (approach + behavior)
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

1. Read `specs/<feature>/AGENTS.md` and `implementation.md`
2. Check the Phase and Blocked status
3. Review `design.md` if you need architectural context
4. Run any existing examples to see current state
5. Pick up from the Next items in `implementation.md`
6. Update `implementation.md` as you work
