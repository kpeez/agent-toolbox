---
name: tdd
description: "Behavioral testing discipline — use disposable real-code probes, then retain only the smallest stable sensor for meaningful public behavior, an actual regression, or a high-risk invariant. Use when implementing or changing behavior, or to de-risk an approach first. Triggers: 'tdd', 'blueprint this', 'prototype', 'spike', 'play with it', 'try a few designs'. Coordinated by /implement."
---

# Behavioral testing, sketch-first

**Use scratch probes to learn, then retain only the smallest stable evidence
that uniquely protects meaningful behavior.**

Tests are not a required output of every change. There is no red/green
choreography, test-per-goal rule, coverage quota, or mutation-score target.
Every promised behavior still needs evidence, but that evidence may be a
committed test, a shared workflow, a static check, a reproducible demonstration,
or an explicit decision that no permanent test is warranted.

## The contract

Work through public behavior and independently justified oracles, not source
structure. A test should survive an internal rewrite because it protects a
caller-visible outcome, a real defect, or a high-risk invariant at a stable
public seam. Scratch scripts may use whatever route helps exploration; when one
earns permanence, preserve the demonstrated behavior, independent oracle, and
stable public boundary — not the exact script, import, or call path.

Work through one **behavioral risk or equivalence class** at a time. One property
or representative workflow may protect several examples or spec claims. Test
count is not progress.

## The loop

### 1. Name the risk and oracle

Before choosing a test style, state:

- the promised behavior, observed defect, or high-risk invariant;
- the independent oracle — how the expected result is known without copying or
  calling production logic; and
- the narrowest stable public seam that exposes the behavior.

If any of those remain unclear, explore before committing a test.

### 2. Probe when useful

Use runnable scratch scripts under `tests/temp/` when the behavior, interface,
or oracle is uncertain (ensure the directory is gitignored). Exercise real
imports, types, and call sites rather than a toy reconstruction. Prints,
ad-hoc drivers, and side-by-side variants are welcome during diagnosis.

Scratch probes are disposable:

1. Name the behavior or question (`verify_replay_buffer_sampling.py`).
2. Give the probe one command to run and a meaningful exit status.
3. Surface enough state to diagnose the result; permanent tests later assert
   only the smallest behavior that matters.
4. Do not polish, persist, or treat the probe's structure as a contract.

A probe may answer whether a path works, whether a state model is coherent, or
which interface is clearest. While it is active, rerun it rather than keeping a
separate run log. For tracker-linked work, record the relevant result on the
issue.

### 3. Select the evidence

Use the first applicable technique:

1. **A real bug occurred** — keep one deterministic regression through a public
   boundary.
2. **Many inputs share a broad independent invariant** — keep one property test
   for that equivalence class.
3. **Sequences or state transitions are the behavior** — use a small stateful
   or model-based property test.
4. **Risk crosses a public system boundary** — keep one representative
   integration or contract workflow using the real client where practical.
5. **The suite may be weak around uncertain changed core logic** — run a
   targeted mutation audit; add a test only for a credible surviving fault.
6. **None applies** — add no permanent test. Use the probe, a type or static
   check, an assertion, or a reproducible PR demonstration as the evidence.

See [references/tests.md](references/tests.md) for the admission gate and the
property and mutation rules.

### 4. Settle

By publication time:

- Each observable claim names its oracle and evidence mode. Exact committed
  test names are recorded after exploration, when tests actually earned a
  place.
- `tests/temp/` is empty. A probe either became stable evidence or ended in a
  recorded verdict and was deleted.
- Verdict-only probes record the question, result, evidence, and next action in
  an ADR for a durable decision, otherwise in the spec Decisions section or
  tracker issue.
- Checks that cannot run in CI first substitute small real things per
  [references/mocking.md](references/mocking.md). If that fails, retain the
  checkable subset and use an explicit demonstration for the rest.

Run lint, types, the existing suite, and the behavior-specific verification
before calling the work done. A failing required gate is a stop.

Once the evidence is green, look for
[refactor candidates](references/refactoring.md) — extract duplication, deepen
modules, move logic to where its data lives — and re-run the evidence after
each step.

## Earn permanent tests

A committed test earns its maintenance cost only when all five answers are
strong:

1. **Behavior** — What caller-visible behavior, actual defect, or high-risk
   invariant does it protect?
2. **Oracle** — Is the expected result independent of production and incidental
   structure?
3. **Uniqueness** — What plausible failure does it catch that the existing
   suite, type checker, linter, assertion, or shared workflow does not?
4. **Seam** — Does it exercise the narrowest stable public boundary and survive
   an internal rewrite?
5. **Cost** — Is it deterministic, legible, and proportionate to the protected
   risk?

Loudness alone does not decide. A loud but costly, recurring, important, or
safety-relevant failure may deserve a regression. A silent failure with a
circular oracle or duplicate sensor does not. If the five-part case is weak,
keep the evidence disposable or record why no permanent test is appropriate.

## Plan before probing

Before writing code:

- [ ] List the behavioral risks or equivalence classes, observable claims, and
      independent oracles.
- [ ] Identify the stable public seams and the cheapest acceptable evidence
      modes.
- [ ] Confirm unresolved interface changes with the user. In a non-interactive
      workflow, report `NEEDS_CONTEXT` with the specific question to the
      orchestrator instead of guessing.
- [ ] Respect the project's glossary and ADRs; use its domain language in claims
      and tests.
- [ ] Look for deep modules and testable boundaries (see
      [../codebase-design/SKILL.md](../codebase-design/SKILL.md) and
      [references/mocking.md](references/mocking.md)).

## Kill mock-slop

Test public behavior, not interactions among your own objects. Delete or rewrite
tests that mock internal collaborators, call private methods, assert call counts
or order, query side channels instead of the public interface, or break under an
internal refactor that preserves behavior.

Mock only true external boundaries — model hubs, trackers, paid APIs, schedulers.
Prefer small real substitutes for code you control: tiny random-weight models,
synthetic media, CPU tensors, or scratch stores. At a service or message boundary,
exercise the consumer's real client and assert only facts that matter to that
consumer; avoid broad exact payload matching and permutation grids.

For a long-running autonomous exploration with a metric target and many
experiments, use `lab:autoresearch`. A scratch probe answers a bounded question
in one sitting.
