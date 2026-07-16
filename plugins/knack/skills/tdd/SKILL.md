---
name: tdd
description: "Functional-test discipline — sketch the intended workflow as scratch scripts in tests/temp/, then refactor the exact scripts that hold up into committed pytest tests that prove the stated goals. Use when implementing or changing behavior, or to de-risk an approach first. Triggers: 'tdd', 'blueprint this', 'prototype', 'spike', 'play with it', 'try a few designs'. Coordinated by /implement."
---

# Functional tests, sketch-first

**Sketch the workflow as scratch scripts → refactor the survivors into committed
tests. Every stated goal ends up with a functional test; trivia gets none.**

This is not strict TDD. There is no red/green choreography and no requirement
that a test exist before the code. The contract is simpler: by the time the
work is published, each stated goal — the behaviors the spec or issue actually
promises — is proven by a committed test that exercises the real code path.

## The rule

Test the stated goals through public interfaces, not implementation details.
The code can be rewritten entirely and the tests shouldn't have to change. A
good test reads like a specification — "future frames cannot affect past
logits" tells you what invariant holds, not how it's enforced. Don't test
config loading, wiring, or trivial code, and don't mock for the sake of it —
test what the feature claims to do.

## The loop

### 1. Sketch

Write runnable scratch scripts under `tests/temp/` (ensure it's gitignored —
add the entry if missing). This is where you play: real imports, real types,
real call sites — never a toy reconstruction. Print statements, ad-hoc
drivers, side-by-side variants are all fine. The more of the actual codebase a
script exercises, the more its result means.

Scratch script rules:

1. **Named for the behavior it probes** (`verify_replay_buffer_sampling.py`),
   not `example.py` or `test.py`. Exits 0/non-zero and prints what it checks.
2. **One command to run** (`python <path>`, `uv run <path>`, `pnpm <name>`).
3. **Surface the state.** Print/render the full relevant state on every action
   or variant switch.
4. **No polish.** No abstractions, no persistence — if the question needs a
   store, hit a scratch one named "SCRATCH — wipe me".

Identify the question each script answers — from the prompt, the surrounding
code, or by asking:

- **"Will this implementation actually work?"** → drive the planned code path
  with real inputs.
- **"Does this logic / state model feel right?"** → tiny interactive script;
  surface the full state after every action. Usually verdict-only.
- **"What should this look like?"** → a few radically different variations on
  one entry point, switchable with a flag, compared side by side.

While a script is in flight, the script is the record — rerun it; don't keep a
separate run log. For tracker-linked work, paste the run result into the issue
comment.

### 2. Refine

As the implementation stabilizes, **refactor those exact scripts — don't
rewrite them.** Prints become asserts, ad-hoc drivers become fixtures, and the
file moves from `tests/temp/` into the project's test suite as a proper pytest
test. The graduated test must exercise the same real imports and call path the
scratch script did — never a polished test that quietly checks something
easier than what you actually verified. The earn-the-test bar below applies.

### 3. Settle

By PR time:

- Every stated goal has a functional test in the committed suite, and the
  spec's Verification section names those tests — committed tests are the
  record.
- `tests/temp/` is empty. Each script either **graduated** into the suite or
  reached one of these ends:
  - **Verdict** — it only answered a design question. Capture the question,
    result, evidence, and next action in plain Markdown: an ADR in `docs/adrs/`
    (see `sharpen`'s `ADR-FORMAT.md`) for durable decisions, otherwise the
    spec's `SPEC-<slug>.md` Decisions section or the tracker issue. Then
    delete the script.
  - **Can't run in CI** (real weights, GPU, paid API, human judgment) — first
    substitute small real things per
    [references/mocking.md](references/mocking.md); if that genuinely fails,
    graduate the checkable subset and delete the rest. The Verification
    section names only committed tests.

Scaffolding never lingers. Run lint/types/tests before calling it done.

## Earn the test

Before graduating (or writing) any test, answer: **what silent bug does this
catch?** A silent bug runs to completion and produces wrong numbers, leaked
data, or a broken invariant. A loud bug throws a traceback on the first real
run — the interpreter already tests for those, and re-testing them is theater:

- Constructor/config smoke tests, registry/wiring assertions
  (`assert cls is FooAnnotator`)
- Restating constants from the source (`assert m.model_id == "org/Model-2B"`)
- Testing the language or framework (an ABC raises `TypeError`)
- Asserting a mock was called with the arguments you just passed
- Tests that `pytest.skip` when weights, GPUs, or caches are absent

If you can't name the silent bug, don't graduate the script — record the
verdict and delete it. **Test count is not a progress metric** — five tests
that pin invariants beat fifty that restate the source, and deleting theater
is as valuable as adding coverage. See
[references/tests.md](references/tests.md) for what earns its place (parity
with a reference implementation, mathematical invariants, gradient flow, data
integrity, round-trips) with worked examples.

## One goal at a time

The failure mode — and the one agents fall into most — is bulk-writing tests
for every goal up front. Bulk-written tests verify _imagined_ behavior and
assert on shape (signatures, data structures) instead of what callers actually
care about. Work vertically instead: sketch one goal, refine it, graduate it,
then move to the next. Each cycle responds to what the previous one taught
you.

## Plan before sketching

When exploring the codebase, use the project's domain glossary so test names
and interface vocabulary match the project's language, and respect ADRs in the
area you're touching. Before writing code:

- [ ] List the stated goals to prove (not implementation steps), and name the
      silent bug each guards against ([references/tests.md](references/tests.md))
- [ ] Confirm with the user what interface changes are needed
- [ ] Identify opportunities for
      [deep modules](references/deep-modules.md) — small interface, deep
      implementation
- [ ] Design interfaces for testability — inject boundaries, return results
      ([references/mocking.md](references/mocking.md))

You can't test everything — concentrate on the promised behaviors and complex
logic, not every edge case. Once graduated tests are green, look for
[refactor candidates](references/refactoring.md): extract duplication, deepen
modules, move logic to where its data lives. Re-run tests after each refactor
step.

## Test quality — kill mock-slop

Bad tests ("mock-slop") couple to internal structure. Delete or rewrite them on
sight. Red flags:

- Mocking your own classes/modules or internal collaborators
- Testing private methods, or asserting on call counts/order
- Verifying through a side channel (querying the DB directly) instead of the
  interface
- The test breaks when you refactor but behavior didn't change
- The test name describes HOW, not WHAT

**Mock only at system boundaries** — model hubs, trackers, paid APIs,
schedulers. Never mock anything you control: substitute small real things
instead (a tiny random-weight model, a synthetic video, CPU tensors). If a
boundary is hard to mock, that's a design signal: inject the dependency and
prefer specific ports over one generic fetcher. See
[references/mocking.md](references/mocking.md) for the substitution patterns.

For a _long-running, autonomous_ exploration with a metric target and many
experiments, use `lab:autoresearch` instead — it manages worktrees, named
experiment groups, and result logging. A scratch script is for a question you
resolve in one sitting.

> Delegate substantial reads and writes per **`/delegate`** — explore with a
> fast model, draft code with a medium one, and review the diff. Don't burn your
> own context.
