---
name: spec
description: Create feature specs for context continuity across agent sessions. Use when starting a new feature or when user runs /spec new.
---

# /spec - Feature Spec Management

## Commands

### /spec new <name>

Creates a feature spec directory with standard template files.

#### Steps

1. Slugify the name: lowercase, replace spaces with hyphens
2. Check if `specs/<slug>/` already exists—if so, error
3. Create `specs/<slug>/` directory
4. Create the five template files below
5. After creation, populate AGENTS.md based on the user's feature request:
   - **Overview**: what the user asked for (from conversation context)
   - **Key Files**: initial guesses based on the feature scope
   - **Quick Start**: first steps for implementation
   - **Conventions**: leave as placeholder if none are known yet

#### Template Files

Create these files in `specs/<slug>/`:

**AGENTS.md**:
```
# <Title> - Agent Instructions

Read this file first when working on this feature.

## Overview
<!-- 1-2 sentences: what we're building and why -->

## Key Files
<!-- update as you work. format: `path/to/file.ts` - purpose -->

## Conventions
<!-- feature-specific patterns, constraints, or gotchas -->

## Quick Start
<!-- for a new agent: what to read first, what to do first -->
```

**design.md**:
```
# <Title> - Design

## Overview
(brief technical approach - fill in during design phase)

## Key Components
(to be defined)

## Data Flow
(to be defined)
```

**ledger.md**:
```
# <Title> - Ledger

## Status
- **Phase**: design
- **Blocked**: no

## Done
(nothing yet)

## Next
- [ ] Define the technical approach

## Context
(gotchas, non-obvious things discovered)
```

**decisions.md**:
```
# <Title> - Decisions

Log non-obvious technical choices here.

---

(No decisions recorded yet)
```

**future-work.md**:
```
# <Title> - Future Work

Ideas and improvements deferred for later.

(Nothing yet)
```
