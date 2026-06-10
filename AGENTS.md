# AGENTS.md

## Guiding principles

- **Do NOT end turns by offering to do more work.** No "Want me to scaffold X?" / "Should I rewrite Y?" engagement-bait offers. The user will explicitly say when they want something done. Answer what was asked, then stop.
- "Done" means "ran it." Example failures = spec failures.

## Spec Workflow

1. Read this file and README.md
2. Check `specs/` for feature specs — read the spec's `SPEC.md` and its tracker
   container/issues before working
3. Inspect existing patterns before adding new ones
4. Implement → lint → types → tests
5. Verify: run examples, fix failures first
6. Status and tasks live on the issue tracker, not in a local file — use
   `/to-issues` to slice a spec into issues; resume by reading the issue

> For non-trivial features, create a spec first with `/write-spec new <name>`.

Specs are private working context and must never be committed. Keep `specs`
ignored in git and prefer a repo-local symlink to a private specs directory,
for example `~/Documents/specs/<repo>`.

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
