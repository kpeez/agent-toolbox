---
name: tdd
description: "Test-Driven Development discipline — spike uncertain designs against the real repo, then one failing test → minimal code, repeated across vertical slices. Use when implementing or changing behavior, or to de-risk an approach first. Triggers: 'tdd', 'blueprint this', 'prototype', 'spike', 'play with it', 'try a few designs'. Coordinated by /implement."
---

# Test-Driven Development

**One test → one implementation → repeat. Vertical slices, never horizontal.**

## The rule

Test behavior through public interfaces, not implementation details. The code can
be rewritten entirely and the tests shouldn't have to change. A good test reads
like a specification — "future frames cannot affect past logits" tells you what
invariant holds, not how it's enforced.

## Choose your entry

- **Behavior already known** — you can name the invariant and the silent bug it
  guards against → go straight to a failing test.
- **Design uncertain** — you don't yet know whether the approach works or which
  shape it should take → [spike first](#spike-first-when-the-design-is-uncertain),
  then graduate what holds up into the test suite.

## Earn the test

Before writing any test, answer: **what silent bug does this catch?** A silent
bug runs to completion and produces wrong numbers, leaked data, or a broken
invariant. A loud bug throws a traceback on the first real run — the
interpreter already tests for those, and re-testing them is theater:

- Constructor/config smoke tests, registry/wiring assertions
  (`assert cls is FooAnnotator`)
- Restating constants from the source (`assert m.model_id == "org/Model-2B"`)
- Testing the language or framework (an ABC raises `TypeError`)
- Asserting a mock was called with the arguments you just passed
- Tests that `pytest.skip` when weights, GPUs, or caches are absent

If you can't name the silent bug, don't write the test. **Test count is not a
progress metric** — five tests that pin invariants beat fifty that restate the
source, and deleting theater is as valuable as adding coverage. See
[references/tests.md](references/tests.md) for what earns its place (parity
with a reference implementation, mathematical invariants, gradient flow, data
integrity, round-trips) with worked examples.

## Spike first (when the design is uncertain)

A spike is **runnable scratch code that proves a planned implementation against
the real repo** — real imports, real types, real call sites, never a toy
reconstruction. The more of the actual codebase it exercises, the more its
result means. Build the smallest component that drives the idea end-to-end and
watch it work (or fail) for real. For ML/research this is the default loop.

Identify the question first — from the prompt, the surrounding code, or by
asking:

- **"Will this implementation actually work?"** → drive the planned code path
  with real inputs.
- **"Does this logic / state model feel right?"** → tiny interactive script;
  surface the full state after every action. Usually verdict-only.
- **"What should this look like?"** → a few radically different variations on
  one entry point, switchable with a flag, compared side by side.

If genuinely ambiguous and the user isn't reachable, default to whichever
matches the surrounding code and state the assumption at the top of the spike.

Spike rules:

1. **Named for the behavior it probes** (`verify_replay_buffer_sampling.py`),
   not `example.py` or `test.py`. Exits 0/non-zero and prints what it checks.
2. **One command to run** (`python <path>`, `uv run <path>`, `pnpm <name>`).
3. **Next to the module it exercises**, but clearly marked as scaffolding, not
   production. No polish, no abstractions, no persistence — if the question
   needs a store, hit a scratch one named "SPIKE — wipe me".
4. **Surface the state.** Print/render the full relevant state on every action
   or variant switch.
5. **Red before green.** A promote-bound spike should fail before the
   implementation exists, then pass once you write it.

**Two exits, never a third:**

- **Graduate** — the spike becomes the first red test. Graft the validated
  slice into the codebase where it belongs, convert the script into a
  behavior-level test in the project's suite (same real imports and call path,
  assertions instead of prints, the earn-the-test bar applies), delete the
  scaffold, and run lint/types/tests before calling it done. If the
  demonstration can't run in CI (real weights, GPU, paid API, human judgment),
  first substitute small real things per
  [references/mocking.md](references/mocking.md); only if that genuinely fails
  may it stay as a clearly-marked script next to the module.
- **Verdict** — the spike only answered a design question. Capture the
  question, result, evidence, and next action in plain Markdown: an ADR in
  `docs/adr/` (see `sharpen`'s `ADR-FORMAT.md`) for durable decisions,
  otherwise the spec's `SPEC-<slug>.md` Decisions section or the tracker issue.
  Then **delete** the code. If the user isn't reachable, leave a placeholder
  with the question so the verdict is filled in before deletion. Scaffolding
  never lingers.

While a spike is in flight, the script is the record — rerun it; don't keep a
separate run log. Once graduated, the committed test is the record. For
tracker-linked work, paste the run result into the issue comment.

For a _long-running, autonomous_ exploration with a metric target and many
experiments, use `lab:autoresearch` instead — it manages worktrees, named
experiment groups, and result logging. A spike is for a question you resolve in
one sitting.

## Vertical, never horizontal

The failure mode — and the one agents fall into most — is writing every test
first (all red), then implementing to chase each one. Bulk-written tests verify
_imagined_ behavior and assert on shape (signatures, data structures) instead of
what callers actually care about.

```
WRONG (horizontal):
  RED:   test1 test2 test3 test4 test5
  GREEN: impl1  impl2  impl3  impl4  impl5

RIGHT (vertical):
  test1 → impl1   (red → green)
  test2 → impl2   (red → green)
  test3 → impl3   (red → green)
```

Each cycle responds to what the previous one taught you. Never refactor while
red — get to green first.

## Workflow

### 1. Plan

When exploring the codebase, use the project's domain glossary so test names
and interface vocabulary match the project's language, and respect ADRs in the
area you're touching.

Before writing any code:

- [ ] Confirm with the user what interface changes are needed
- [ ] Confirm which behaviors to test (prioritize), and name the silent bug
      each one guards against ([references/tests.md](references/tests.md))
- [ ] Identify opportunities for
      [deep modules](references/deep-modules.md) — small interface, deep
      implementation
- [ ] Design interfaces for testability — inject boundaries, return results
      ([references/mocking.md](references/mocking.md))
- [ ] List the behaviors to test (not implementation steps)
- [ ] Get user approval on the plan

Ask: "What should the public interface look like? Which behaviors are most
important to test?" You can't test everything — concentrate on critical paths
and complex logic, not every edge case.

### 2. Tracer bullet

Write ONE test that confirms ONE behavior → red. Write the minimal code to
pass it → green. This proves the path works end-to-end.

### 3. Incremental loop

For each remaining behavior: write the next test (red) → minimal code (green).

- One test at a time
- Only enough code to pass the current test
- Don't anticipate future tests
- Keep tests focused on observable behavior

### 4. Refactor

Only once green. Look for
[refactor candidates](references/refactoring.md): extract duplication, deepen
modules, move logic to where its data lives, consider what the new code reveals
about existing code. Re-run tests after each refactor step. Never refactor
while red.

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

> Delegate substantial reads and writes per **`/delegate`** — explore with a
> fast model, draft code with a medium one, and review the diff. Don't burn your
> own context.
