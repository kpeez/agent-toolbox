# Test value

Read this reference before committing a permanent test and throughout a test
audit. One bar applies both ways: the admission gate rejects a new test that
matches a junk pattern, and an audit hunts for existing tests that do.

The test carries the burden of proof. After reading the complete test and its
production owner, a test whose contract and credible regression cannot be
named is a deletion candidate. A test that names a contract stays until a
stronger keeper for that contract is verified.

## Junk patterns

- assertion-free coverage probes, and non-crash checks where a value or
  invariant oracle exists;
- self-comparisons and identity copiers;
- expected values produced by the code under test, copied from its output, or
  held in broad snapshots accepted without independent review;
- copied fixtures, constants, registries, inventories, manifests, or export
  lists restated in the test;
- exact source, import, or string greps;
- private methods, predicates, internal call counts, or mock call order or
  shape, when the behavior is observable at a real boundary;
- mocks that implement the asserted behavior, or one identical mock standing in
  for different APIs;
- fixtures that supply the result, ordering, or callback the owner should
  produce, or persistence asserted against a store the path never writes;
- framework or language behavior the dependency already guarantees;
- tests that restate declared flags or config instead of exercising the
  behavior the flag promises;
- duplicate invocations of one contract: every permutation of one equivalence
  class, each validation branch or wiring path already exercised by one
  boundary test, the same scenario replayed at every layer, or a local replay
  of a shared helper's tests;
- tests whose only purpose is keeping test-only exports, globals, wrappers,
  injection hooks, or dead production code alive;
- negative controls that pass for an unrelated reason, such as a rejection from
  a different guard or a path production never reaches;
- names or fixtures that promise more than the assertions check;
- tests that exist only to raise coverage.

## Retention bar

Keep a test, including one that matches a junk pattern, when it independently
enforces a public API, plugin or extension SDK, CLI, protocol, config or file
format, migration, storage, security, platform, default value, exact prompt or
model-facing text, generated or cross-language output, packaging, release, or
architecture contract. Also keep:

- call ordering when order is observable behavior;
- a regression with a credible failure mode at its owner boundary;
- source inspection when it is the cheapest independent guard: it fails when
  the contract changes (the user-facing key, byte, or path) and survives an
  identifier-only refactor;
- a retained test that fails on the baseline: treat it as a possible product
  bug, reproduce it, and repair the owner rather than deleting the test.

Static or slow is not a deletion reason on its own. A test that resembles
implementation may still be the only proof of a contract; prove otherwise
before removing it. Remove redundant examples only after a clearer property or
representative workflow demonstrably preserves their distinct useful coverage.

Good tests assert caller-relevant values or invariants at stable public seams,
run without network or cache state, and fail for one credible product reason.
