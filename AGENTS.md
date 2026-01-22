# AGENTS.md

This file is for coding agents. It captures language-agnostic workflow, conventions, and principles that should hold across repos.

## Scope & priority

- Obey this file first; then README.md; then in-code comments/docstrings.
- If a subdirectory has its own AGENTS.md, the closest one wins.
- Keep this file current whenever conventions change—stale guidance causes bad diffs.

## How to work on a task

1) Read this file, README.md, and any relevant language profile.
2) Inspect existing patterns before adding new ones.
3) Implement with the guidelines below.
4) Self-check: lint → types → tests (using language-appropriate tooling).
5) Verify via examples: run examples that exercise your changes.
6) Produce concise, technical notes in the PR/summary (what changed, why, risks).

## Verification via examples

For features that produce executable code, "done" means "ran it successfully"—not just "wrote it."

### Per-spec examples (default)

Add `examples/` to the spec folder for feature-specific verification:

```text
specs/<feature>/
├── design.md
├── ledger.md
├── examples/
│   ├── basic_usage.py    # minimal working example
│   └── TEST_LOG.md       # execution results
```

Keep these atomic and focused—one example per behavior you're verifying.

### Project-wide examples (optional)

For libraries or frameworks, maintain a top-level `examples/` or `cookbook/` directory:

```text
examples/              # or cookbook/
├── getting-started/
│   ├── README.md
│   ├── hello_world.py
│   └── TEST_LOG.md
├── advanced-patterns/
│   └── ...
```

Use for user-facing tutorials, pattern demonstrations, or integration scenarios.

### TEST_LOG.md format

After running an example, log the result:

```markdown
### basic_usage.py
**Status:** PASS
**Date:** 2025-01-15
**Description:** Verifies the auth flow with valid credentials.
**Result:** Token returned, expires_in=3600.
---
```

Update this log every time you run the example. Treat example failures as spec failures—don't mark a feature done until examples pass.

### Workflow integration

1. Write or update examples that exercise your changes
2. Run each example
3. Update TEST_LOG.md with PASS/FAIL and observations
4. Fix failures before considering the task complete

> **Tip:** If an example fails, that's signal—either the code is wrong or the example's expectations are stale. Investigate before moving on.

## Feature specs (context continuity)

The `specs/` folder contains design documents for current tasks. They preserve context across sessions, enabling any new agent to pick up where the last left off.

**Always read the design document before jumping into doing work!**

> **Tip:** Store specs in a cloud-synced location (`~/Documents/specs/<repo>/`) and symlink into each repo for backup and portability.

Each spec lives in its own folder: `specs/<feature>/` with the following files (created by `/spec new`):

```text
specs/<feature>/
├── AGENTS.md           # Spec-specific instructions (always read first)
├── CLAUDE.md           # References AGENTS.md for Claude Code auto-discovery
├── design.md           # Source of truth: technical approach, architecture, data flow
├── ledger.md           # Current status and what's done
├── decisions.md        # Captures the "why" (i.e., decision traces)
├── future-work.md      # What's deferred, ideas for later improvements
└── examples/           # Optional: runnable verification examples
    ├── basic_usage.py
    └── TEST_LOG.md
```

4Keep them lightweight: a one-liner is fine if there's nothing to say yet. The structure prompts thinking and helps future sessions know where to look.

### Ledger example

```markdown
# specs/<feature>/ledger.md

## What
<1-2 sentences: what we're building>

## Ledger
- **Phase**: design | implementing | testing | done
- **Blocked**: no | yes (reason)

## Done
- [x] completed item

## Next
- [ ] next item
- [ ] after that

## Context
<gotchas, non-obvious things, key files touched>
```

### Decisions

When making non-obvious technical choices, append to `specs/<feature>/decisions.md`:

```markdown
## <Decision Title>
**Context**: <why this decision was needed>
**Decision**: <what we chose>
**Alternatives**: <what else was considered>
**Rationale**: <why this option>
```

Don't create ceremony - only log decisions that future-you would wonder about.

### Skills

- `/spec new <name>` — create a new feature spec
- `/handoff` — capture session context before ending

### Workflow

1. Check `specs/` when starting work on a feature
2. Read the AGENTS.md (and/or CLAUDE.md) in that folder
3. Review the `design.md` if needed
4. Check `ledger.md` for current status and next tasks
5. Update `ledger.md` as you work (especially Done/Next/Context)

### Auto-discovery

**Important**: `specs/` is gitignored and won't appear in search results or @ autocomplete. Always check explicitly by listing the directory path.

When starting ANY task:

1. List `specs/` directory at project root (even if it doesn't appear in searches)
2. If specs exist, read the relevant spec's `AGENTS.md` and `ledger.md` before proceeding
3. Only create a new spec (`/spec new`) if no matching spec exists

---

## Coding design principles

- Write elegant code; choose the simplest construct that expresses intent.
- Never duplicate behavior; remove or reuse existing helpers instead of adding near-duplicates.
- Names must be descriptive with auxiliaries (`is_active`, `has_permission`, `should_retry`). Avoid cryptic abbreviations.
- Use RORO (receive an object, return an object) for complex parameters/results. Prefer keyword-only args for clarity.
- Replace literals with named constants; keep constants at the top of a module or in a dedicated constants file.
- Keep modules small; group related code.

### Comments & documentation

- Comments are only for *why*, never for *what*. Do not restate code. All comments lowercase and concise.
- Prefer docstrings for public functions/classes when intent or side effects aren't obvious.
- Avoid "slop comments" like `# do thing`; remove or rewrite them as justification or design notes.

### Error handling

- Don't over-guard or be overly defensive; raise/catch only when a failure is expected or actionable.
- Fail fast with clear messages; avoid silent passes.

### Testing

- Keep tests small, focused, and readable; mirror source layout under `tests/`.
- Test edge cases and regression paths. Write/adjust tests before fixing bugs when feasible.

### Performance & quality

- Run lint, type checks, and relevant tests locally before handing off. Aim for clean, actionable diffs.
- Default to small, reviewable changes; avoid repo-wide rewrites unless requested.

### Dependencies

- Minimize new deps; justify every addition. Prefer stdlib first, then existing project deps. No heavy/unstable packages without approval.
- Remove dead deps when noticed.

### Security & data

- Never commit secrets; respect `.gitignore`/`.ignore`. Use environment variables for credentials.
- Be cautious with file IO and network calls; follow least-privilege defaults.

### Pull requests & git hygiene

- Keep commits logically scoped; write imperative, specific messages.
- Ensure formatting/lint/type/tests pass before raising a PR.

### Updating this file

- When conventions change (workflow, style, test strategy), update here first.
- Keep instructions specific and actionable; avoid vague rules.
