# AGENTS.md

## Priority

This file > README.md > in-code comments. Closest AGENTS.md wins in subdirectories.

## Workflow

1. Read this file, README.md, and relevant language profile
2. Check `specs/` for feature specs (gitignored—list explicitly)
3. If spec exists: read its AGENTS.md + implementation.md before working
4. Inspect existing patterns before adding new ones
5. Implement; self-check: lint → types → tests
6. Verify: run examples exercising changes, update TEST_LOG.md, fix failures first
7. Concise PR notes (what changed, why, risks)

## Feature specs

`specs/` preserves context across sessions. Created by `/spec new`, captured by `/handoff`.

**Index**: `specs/INDEX` (TSV: slug, phase, blocked, desc) — overview of all specs.

**Files per spec**: AGENTS.md, CLAUDE.md, design.md, implementation.md, decisions.md, future-work.md, examples/

**implementation.md format**:

```
## Status
- **Phase**: design | implementing | testing | done
- **Blocked**: no | yes (reason)
## Done
- [x] completed item
## Next
- [ ] next item
## Context
<gotchas, key files>
```

**decisions.md**: append non-obvious choices with Context, Decision, Alternatives, Rationale.

**Spec workflow**: read AGENTS.md + implementation.md → work → update implementation.md → `/handoff` before ending.

## Verification

"Done" means "ran it"—not "wrote it." Add `examples/` to spec folder, one per behavior.

**TEST_LOG.md entry**: `### name` / Status: PASS|FAIL / Date / Description / Result

Fix failures before marking done. Example failures = spec failures.

## Coding principles

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

- State assumptions explicitly — if uncertain, ask rather than guess
- Present multiple interpretations — don't pick silently when ambiguity exists
- Push back when warranted — if a simpler approach exists, say so
- Stop when confused — name what's unclear and ask for clarification

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked
- No abstractions for single-use code
- No "flexibility" or "configurability" that wasn't requested
- No error handling for impossible scenarios
- If 200 lines could be 50, rewrite it

**The test:** Would a senior engineer say this is overcomplicated? If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:

- Don't "improve" adjacent code or formatting
- Don't refactor things that aren't broken
- Match existing style, even if you'd do it differently
- If you notice unrelated dead code, mention it — don't delete it

When your changes create orphans:

- Remove imports/variables/functions that YOUR changes made unused
- Don't remove pre-existing dead code unless asked

**The test:** Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform imperative tasks into verifiable goals:

| Instead of...    | Transform to...                                       |
|------------------|-------------------------------------------------------|
| "Add validation" | "Write tests for invalid inputs, then make them pass" |
| "Fix the bug"    | "Write a test that reproduces it, then make it pass"  |
| "Refactor X"     | "Ensure tests pass before and after"                  |

For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

### Style & hygiene

- Never duplicate behavior; reuse existing helpers.
- Descriptive names with auxiliaries (`is_active`, `has_permission`, `should_retry`).
- RORO for complex params/results. Keyword-only args for clarity.
- Named constants over literals. Small focused modules.
- Comments only for _why_, never _what_. No slop comments. Docstrings for non-obvious public APIs.
- Fail fast with clear messages. No silent passes.
- Small focused tests mirroring source layout. Test edge cases. Tests before bug fixes.
- Minimize deps (stdlib first); justify additions. Remove dead deps.
- Never commit secrets; use env vars. Respect `.gitignore`.
- Small reviewable commits; imperative messages. Lint/types/tests pass before PR.

Update this file first when conventions change.
