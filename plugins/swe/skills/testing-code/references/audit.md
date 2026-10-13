# Test audit detail

Read this reference in audit mode. The numbered audit procedure in
[SKILL.md](../SKILL.md) names the steps. This file holds the detail for each
step.

Shrink a test suite to the tests that earn their cost. Every surviving test
should name the contract it guards and the regression it catches. Expect large
cuts in suites that were written without that bar. Deletion count is not the
goal: do not delete a test that still names a contract with no verified keeper.

Audit mode has two sizes. Both share one value bar:

- **Audit:** a focused sweep that prepares one coherent batch of deletions,
  consolidations, and repairs for review. Continue broad audits as follow-up
  batches or PRs when publication is authorized.
- **Campaign:** prune one subsystem's whole test surface, every test file a
  package or area owns, in one reviewable change. Read
  [campaign.md](campaign.md) first.

## Value bar

Read [the test value bar](test-value.md). Its junk patterns, retention bar, and
burden of proof decide every mark. An existing test that must change for a
behavior-preserving refactor is suspect, not automatically deletable.

Before judging a candidate, read root and scoped agent instructions, then the
complete test and its production owner: entry point, callers, callees, sibling
implementations, overlapping tests, CI configuration, and relevant history.
When the test claims dependency-backed behavior, inspect the dependency source
or types directly.

## Discovery

Keep discovery read-only and report evidence before editing. For broad scope,
split discovery into parallel read-only lanes along production owner
boundaries, plus one cross-cutting junk-pattern sweep; use
[orchestrate](../../orchestrate/SKILL.md) when delegation is available. Outside
campaign mode, prefer a few high-confidence candidates over a large speculative
inventory.

## Candidate evidence

Mark each candidate by its assertions, not its name:

- `retain`, naming the contract and the bug it catches;
- `repair`, keeping the contract but fixing the assertion, such as a vacuous
  negative that passes when only one of several items is missing;
- `consolidate`, naming the keeper that absorbs the assertion: a sibling
  table case, a stronger boundary suite, or a shared owner;
- `delete`, naming the proof that remains or why no contract exists.

Record every field below for each `repair`, `consolidate`, or `delete` mark
before editing. A missing field means the candidate is not ready:

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

## Validation checks

Do not edit source or tests while a test runner is watching the checkout.

- Record baseline failures separately from the rest. Under the retention bar,
  they may be product bugs.
- After each batch, run the smallest owner and sibling tests with the
  project's runner.
- For each removed source grep or plan assertion, run the executable path that
  owns the real contract.
- For each `consolidate` or `repair` contract, make one deliberate mutation of
  the production owner, confirm the keeper fails, then restore the source byte
  for byte. See [mutation audits](mutation-audits.md).
- Run formatting, `git diff --check`, and the repository's required gates for
  the changed paths.
- Inspect `git diff --numstat`. Report production and tooling lines separately
  from tests and test support.

## Preservation review

Get an independent preservation review of the final diff: compare deleted
coverage against keepers for contracts that lost their only proof, and look for
new assertions that cannot fail. Report an unavailable review as a verification
gap. A second pass by the implementer is not independent review.

## Landing and continuation

If publication is authorized, use [ship-pr](../../ship-pr/SKILL.md) for one
coherent PR at a time. Otherwise report the reviewed local diff and validation
without publishing. After a PR lands, refresh from the default branch and rerun
read-only discovery for the next high-confidence batch.

## Handoff

Report:

- removed low-value categories and why they existed;
- production owner simplifications;
- retained false positives and why they remain valuable;
- baseline failures and their disposition;
- focused and full proof actually run, including caught mutations;
- production versus test line counts;
- PR state and named follow-ups.
