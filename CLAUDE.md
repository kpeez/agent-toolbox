## Guiding principles

- **Do NOT end turns by offering to do more work.** No "Want me to scaffold X?" / "Should I rewrite Y?" engagement-bait offers. The user will explicitly say when they want something done. Answer what was asked, then stop.
- "Done" means "ran it." Test failures = spec failures.

## Workflow

The spine is **sharpen → spec → issues → implement → review → PR**. `/start-loop <idea>`
runs it end to end as one resumable command; spec approval is the last user
prompt — after it the loop runs to completion, escalating only real blockers.

The main agent is the orchestrator: route exploration to explorers, plan
drafting to planners, and well-specified writes to doers per `/delegate` —
never burn the lead context on bulk reads or typing implementation.

1. Read this file and README.md
2. For non-trivial features, stress-test the plan with `/sharpen`, then
   `/write-spec new <name>` — the spec (pure-markdown `SPEC-<slug>.md`; its
   behaviors are proven by committed tests) is distilled from the sharpened
   plan, never written from scratch
3. Slice the spec into tracker issues with `/to-issues`. Status and tasks live
   on the tracker, never in local files
4. Implement per `/implement`: prove behavior per `/tdd` — functional tests
   for the stated goals, sketched as `tests/temp/` scratch scripts when the
   design is uncertain — then lint → types → tests
5. Verify: run the spec's tests and a host-native review pass; fix failures before marking done
6. Publish with `/pr` — atomic commits, push, draft PR
7. Resume from the tracker: take the next unblocked workable issue (spec-born
   slices are ready by construction; skip only `ready-for-human`); comment
   progress on the active issue before running out of context

Specs and ADRs must never be committed to the source repository. Store their
canonical shared copies in `$LLMOS_ROOT/projects/<repo>/docs/specs` and
`$LLMOS_ROOT/projects/<repo>/docs/adrs`, keep `specs`, `adrs`, `docs/specs`, and
`docs/adrs` ignored here, and reach them through direct `docs/` links plus exact
relative root aliases.

Durable decisions live as ADRs in the shared vault, reached via the `docs/adrs/`
symlink; the optional domain glossary is the still-committed repo-root
`CONTEXT.md`. An optional `Issue tracker: <name>` line in this file pins the
tracker; otherwise `/to-issues` auto-detects.

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

Every task ends with a verifiable check — a functional test proving the stated
goal, run and passing. When the design is uncertain, sketch the check as a
scratch script in `tests/temp/`, then refactor that exact script into a real
test as the code stabilizes.

- "Add validation" → tests proving invalid inputs are rejected
- "Fix the bug" → a test that reproduces it, then make it pass
- "Refactor X" → ensure tests pass before and after

For multi-step work, state a plan: `[step] → verify: [check]`, one line each.

### Style

- Descriptive names (`is_active`, `has_permission`). Comments only for _why_.
- Reuse helpers. Named constants. Fail fast. No slop.
- Small commits, imperative messages. Lint/types/tests pass before PR.

Update this file first when conventions change.
