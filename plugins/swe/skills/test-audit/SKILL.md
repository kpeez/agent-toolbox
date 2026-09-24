---
name: test-audit
description: "Audit and prune existing tests that are low-value, duplicative, or coupled to implementation, and the test-only production seams they keep alive. Use for test-suite reviews, sweeps, or pruning campaigns; not for designing new tests."
---

# Test audit

Shrink a test suite to the tests that earn their cost. Every surviving test
should name the contract it guards and the regression it catches; expect large
cuts in suites that were written without that bar. Deletion count is not the
goal: do not delete a test that still names a contract with no verified keeper.

Two modes share one value bar:

- **Audit:** a focused sweep that lands one coherent batch of deletions,
  consolidations, and repairs per PR. Continue broad audits as follow-up PRs.
- **Campaign:** prune one subsystem's whole test surface, every test file a
  package or area owns, in one PR. Read [CAMPAIGN.md](CAMPAIGN.md) first.

Any test added or rewritten during an audit must pass the
[testing-code](../testing-code/SKILL.md) admission gate, including being seen
red.

## Value bar

Read [the test value bar](../testing-code/references/test-value.md): its junk
patterns, retention bar, and burden of proof decide every mark. An existing
test that must change for a behavior-preserving refactor is suspect, not
automatically deletable.

Before judging a candidate, read root and scoped agent instructions, then the
complete test and its production owner: entry point, callers, callees, sibling
implementations, overlapping tests, CI configuration, and relevant history.
When the test claims dependency-backed behavior, inspect the dependency source
or types directly.

## Discovery

Keep discovery read-only and report evidence before editing. For broad scope,
split discovery into parallel read-only lanes along production owner
boundaries, plus one cross-cutting junk-pattern sweep; use `/orchestrate` when
delegation is available. Outside campaign mode, prefer a few high-confidence
candidates over a large speculative inventory.

## Candidate evidence

Mark each candidate by its assertions, not its name:

- `R` retain, naming the contract and the bug it catches;
- `F` retain the contract but repair the assertion, such as a vacuous negative
  that passes when only one of several items is missing;
- `C` consolidate, naming the keeper that absorbs the assertion: a sibling
  table case, a stronger boundary suite, or a shared owner;
- `D` delete, naming the proof that remains or why no contract exists.

Record every field below for each `F`, `C`, or `D` before editing. A missing
field means the candidate is not ready:

- exact test name and location;
- what failure it can actually detect;
- non-test callers of the covered production or test-support seam;
- the stronger remaining keeper, or why no contract needs proof;
- relevant history and the reason the test or seam exists;
- production or test-support code the change unlocks for deletion;
- risk and the focused validation command.

## Edit shape

Choose one coherent owner-boundary batch. Delete the test-only exports,
globals, wrappers, injection parameters, and dead production paths the removed
tests kept alive instead of preserving aliases. Move retained regressions to
their canonical owners. Consolidate repeated assertions into one table case or
generic contract.

Prefer net-negative production lines. Do not add replacement tests that restate
the same implementation, and do not convert uncertain candidates into cleanup
to increase deletion counts.

## Validation

Do not edit source or tests while a test runner is watching the checkout.

1. Before editing, run the in-scope tests at the starting commit and record
   baseline failures separately; under the retention bar they may be product
   bugs.
2. After each batch, run the smallest owner and sibling tests with the
   project's runner.
3. For each removed source grep or plan assertion, run the executable path that
   owns the real contract.
4. For each `C` or `F` contract, make one deliberate mutation of the production
   owner, confirm the keeper fails, then restore the source byte for byte. See
   [mutation audits](../testing-code/references/mutation-audits.md).
5. Run formatting, `git diff --check`, and the repository's required gates for
   the changed paths.
6. Inspect `git diff --numstat`; report production and tooling lines separately
   from tests and test support.
7. Get an independent preservation review of the final diff: compare deleted
   coverage against keepers for contracts that lost their only proof, and look
   for new assertions that cannot fail.

## Landing and continuation

Publish through `/ship-pr`. Land one coherent PR at a time; after it lands,
refresh from the default branch and rerun read-only discovery for the next
high-confidence batch.

## Handoff

Report:

- removed low-value categories and why they existed;
- production owner simplifications;
- retained false positives and why they remain valuable;
- baseline failures and their disposition;
- focused and full proof actually run, including caught mutations;
- production versus test line counts;
- PR state and named follow-ups.
