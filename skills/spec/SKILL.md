---
name: spec
description: Create and manage feature specs for context continuity across agent sessions. Use when starting a new feature, when the task requires design thinking, touches multiple files, or spans sessions. Invoke with /spec new or when user asks to plan before coding.
---

# /spec - Feature Spec Management

## The spec-first rule

**When this skill is active, you MUST write or update spec docs BEFORE writing any source code.**

The sequence is always: explore → plan → **write spec** → get user confirmation → implement → verify.

If you catch yourself editing source files without a spec that reflects your plan, STOP. Go back and write the spec first. Even a one-line design.md is better than jumping straight to code.

## When to use specs

Use a spec when any of these are true:

- The task requires design thinking or choosing between approaches
- The change touches multiple files or modules
- The work will span more than one session
- You're unfamiliar with the area of the codebase being modified
- The user explicitly asks for a plan or spec

Skip specs for trivial changes — typo fixes, single-line config changes, log line additions, renames.

## Spec-first workflow

1. **Explore**: read code, understand the problem, gather context (use Plan Mode when available)
2. **Plan**: develop a detailed approach — components, data flow, tradeoffs
3. **Write the spec**: create or update `specs/<feature>/` docs with your plan
   - `design.md` — what you're building and how
   - `implementation.md` — status, done, next, context
   - `decisions.md` — any non-obvious choices made during planning
4. **Get user confirmation** on the spec before proceeding
5. **Implement**: write code, verifying against the spec as you go
6. **Verify**: run tests/examples, update TEST_LOG.md, fix failures
7. **Update implementation.md** with final status (Done/Next/Context)

## Commands

### /spec new <name>

Creates a feature spec directory with standard template files.

<steps>
<step action="slugify">lowercase name, replace spaces with hyphens → `<slug>`</step>
<step action="check-exists">error if `specs/<slug>/` exists</step>
<step action="mkdir">`specs/<slug>/`</step>
<step action="create-files">write all templates below to `specs/<slug>/`</step>
<step action="create-examples" condition="feature produces executable code">create `examples/` with TEST_LOG.md</step>
<step action="populate">fill AGENTS.md from conversation context (overview, key files, quick start); fill design.md with the planned approach</step>
<step action="update-index">append row to `specs/INDEX` (create with header `slug\tphase\tblocked\tdesc` if missing)</step>
</steps>

## Spec structure

Each spec lives in `specs/<slug>/` with these files:

```
specs/<feature>/
├── AGENTS.md           # Spec-specific agent instructions (read first)
├── CLAUDE.md           # References AGENTS.md for Claude Code auto-discovery
├── design.md           # Source of truth: what and how
├── implementation.md   # Current status and progress
├── decisions.md        # Non-obvious choices and rationale
├── future-work.md      # Deferred ideas
└── examples/           # Runnable verification examples
    ├── basic_usage.py
    └── TEST_LOG.md
```

**Index**: `specs/INDEX` (TSV: slug, phase, blocked, desc) — overview of all specs.

### design.md

Source of truth for _what_ you're building and _how_. Write this during the planning phase, before implementation.

Contents:

- **Problem statement** — what problem are we solving and why
- **Technical approach** — architecture, key components, patterns used
- **Data flow** — how data moves through the system, key interactions
- **Open questions** — unresolved decisions or unknowns (if any)

Keep it concise. A few paragraphs is fine for most features.

### implementation.md

Tracks progress. Updated throughout the lifecycle.

```
# <Title> - Implementation

## Status
- **Phase**: design | implementing | testing | done
- **Blocked**: no | yes (reason)

## Done
- [x] completed item

## Next
- [ ] next item

## Context
<gotchas, key files touched, non-obvious things>
```

### decisions.md

Append non-obvious technical choices. Only log decisions that future-you would wonder about.

```
## <Decision Title>
**Context**: <why this decision was needed>
**Decision**: <what we chose>
**Alternatives**: <what else was considered>
**Rationale**: <why this option>
```

### examples/TEST_LOG.md

Log results every time you run an example:

```
### <example_name>
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
<!-- problem statement | technical approach | data flow | open questions -->
</template>

<template file="implementation.md">
# <Title> - Implementation

## Status

- **Phase**: design
- **Blocked**: no

## Done

## Next

- [ ] Define the technical approach

## Context

</template>

<template file="decisions.md">
# <Title> - Decisions
<!-- append: ## Title / Context / Decision / Alternatives / Rationale -->
</template>

<template file="future-work.md">
# <Title> - Future Work
</template>

<template file="examples/TEST_LOG.md" condition="feature produces executable code">
# <Title> - Test Log
<!-- format: ### name / Status: PASS|FAIL / Date / Description / Result -->
</template>

</templates>

## Resuming work on an existing spec

When picking up an existing spec:

1. Read `specs/<feature>/AGENTS.md` and `implementation.md`
2. Check the Phase and Blocked status
3. Review `design.md` if you need architectural context
4. Check `decisions.md` for past rationale
5. Pick up from the Next items in `implementation.md`
6. Update `implementation.md` as you work
