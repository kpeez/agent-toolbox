# AGENTS.md

## Priority

This file > README.md > in-code comments. Closest AGENTS.md wins in subdirectories.

## Workflow

1. Read this file and README.md
2. Check `specs/` for feature specs — read AGENTS.md + implementation.md before working
3. Inspect existing patterns before adding new ones
4. Implement → lint → types → tests
5. Verify: run examples, update TEST_LOG.md, fix failures first

> For non-trivial features, create a spec first with `/spec new <name>`.

## Verification

"Done" means "ran it." Example failures = spec failures.

## Code rules

### Think first
- State assumptions. Ask when uncertain. Push back when simpler approaches exist.

### Simplicity
- No abstractions, flexibility, or error handling beyond what was asked
- If 200 lines could be 50, rewrite it
- Inline unless reused. Colocate related logic. Keep functions flat (early returns, one indent level).

### Surgical changes
- Only touch what the request requires. Match existing style.
- Remove orphans YOUR changes created. Don't touch pre-existing dead code.

### Types & state
- Required over optional. Minimize arguments. Const by default.
- Discriminated unions over loose types. Exhaustive handling; fail on unknown.
- Assert shape on inputs — no silent defaults. Trust the type system.

### Goal-driven development

Every task follows a red/green cycle — define a verifiable goal before writing code, then loop until verified.

**Transform vague tasks into testable goals:**

- "Add validation" → write tests for invalid inputs, then make them pass
- "Fix the bug" → write a test that reproduces it, then make it pass
- "Refactor X" → ensure tests pass before and after

**The loop:** Goal → implement → verify → repeat if failing.

**For multi-step work, state a plan:**

1. [Step] → verify: [check]
2. [Step] → verify: [check]

### Style

- Descriptive names (`is_active`, `has_permission`). Comments only for _why_.
- Reuse helpers. Named constants. Fail fast. No slop.
- Small commits, imperative messages. Lint/types/tests pass before PR.

Update this file first when conventions change.
