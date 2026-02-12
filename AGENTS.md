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

- Simplest construct that expresses intent. No speculative features or abstractions.
- Never duplicate behavior; reuse existing helpers.
- Descriptive names with auxiliaries (`is_active`, `has_permission`, `should_retry`).
- RORO for complex params/results. Keyword-only args for clarity.
- Named constants over literals. Small focused modules.
- Comments only for _why_, never _what_. No slop comments. Docstrings for non-obvious public APIs.
- Fail fast with clear messages. No over-guarding or silent passes.
- Small focused tests mirroring source layout. Test edge cases. Tests before bug fixes.
- Minimize deps (stdlib first); justify additions. Remove dead deps.
- Never commit secrets; use env vars. Respect `.gitignore`.
- Small reviewable commits; imperative messages. Lint/types/tests pass before PR.

Update this file first when conventions change.
