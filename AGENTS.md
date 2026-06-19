## Guiding principles

- **Do NOT end turns by offering to do more work.** No "Want me to scaffold X?" / "Should I rewrite Y?" engagement-bait offers. The user will explicitly say when they want something done. Answer what was asked, then stop.
- "Done" means "ran it." Example and test failures = spec failures.

## Workflow

The spine is **grill → spec → issues → implement → PR**.

1. Read this file and README.md
2. For non-trivial features, stress-test the plan with `/grill-me`, then
   `/write-spec new <name>` — the spec (`SPEC.md` + runnable `examples/`) is
   distilled from the grilled plan, never written from scratch
3. Slice the spec into tracker issues with `/to-issues`. Status and tasks live
   on the tracker, never in local files
4. Implement per `/implement`: prove behavior first (failing test via `/tdd`
   or red example via `/blueprint`), then code to green → lint → types → tests
5. Verify: run the examples; fix failures before marking done
6. Publish with `/pr` — atomic commits, push, draft PR
7. Resume from the tracker: take the next unblocked `ready-for-agent` issue;
   comment progress on the active issue before running out of context

Specs are private working context and must never be committed. Keep `specs`
ignored in git and prefer a repo-local symlink to a private specs directory,
for example `~/Documents/specs/<repo>`.

Durable decisions live in committed `docs/adr/`; the optional domain glossary
is repo-root `CONTEXT.md`. An optional `Issue tracker: <name>` line in this
file pins the tracker; otherwise `/to-issues` auto-detects.

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

Every task follows a red/green cycle — define a verifiable check before writing
code, watch it fail, implement until it passes.

- "Add validation" → write tests for invalid inputs, then make them pass
- "Fix the bug" → write a test that reproduces it, then make it pass
- "Refactor X" → ensure tests pass before and after

For multi-step work, state a plan: `[step] → verify: [check]`, one line each.

### Style

- Descriptive names (`is_active`, `has_permission`). Comments only for _why_.
- Reuse helpers. Named constants. Fail fast. No slop.
- Small commits, imperative messages. Lint/types/tests pass before PR.

Update this file first when conventions change.
