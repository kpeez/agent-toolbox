# audit-tests

Applies when: prune or review an existing test suite.

1-record-suite-baseline: Record the suite's pass state, count, and runtime. (test-audit)
2-mark-candidates: Mark each candidate retain, repair, consolidate, or delete with its evidence fields. (test-audit)
3-edit-in-small-batches: Edit one batch and rerun owner tests after each batch. (test-audit, sequence-verifiable-units)
4-mutate-kept-contracts: Show each kept or moved contract still fails under one deliberate mutation. (test-audit, testing-code)
5-independent-preservation-review: Get a review from an agent that did not edit. (reviewer agent)
6-publish-draft-pr: Push the final commits and update the draft PR when publication is authorized. (ship-pr)

Reply: tests and production lines removed, contracts kept, and review result.
