# build-feature

Applies when: new or changed behavior.

You own the design. Plan, review, verify.

Delegate implementation and stay in the lead. Delegation is mandatory and the laziness protocol does not waive it, because the gain is review separation. A subagent that cannot spawn owns the diff directly and keeps the same review separation. Code-coupled work goes to one owner with the checkpoint inline, and that owner fans out after the blocking phase. Parent-level fan-out is for slices with independent artifacts. Rewrite the checkpoint at phase boundaries. Spawn a fresh owner rather than chaining interrupts.

1-map-subsystem: Run how over the affected subsystem. (how)
2-name-data-shape: Name the data shape, its states, their owners, and its organizing structure before logic. Prefer a state machine to scattered booleans and a table to branching. (model-the-domain, foundational-thinking)
3-explore-designs: When the code crosses a function boundary, run architect for parallel design exploration. For a consequential interface, map callers, invariants, and errors. (architect, codebase-design, redesign-from-first-principles)
4-write-throughput-checkpoint: Add four task items for blocking first steps, independent workstreams, shared mutable state, and the smallest safe decomposition. Mark one that does not apply `n/a: <reason>`. (separate-before-serializing-shared-state)
5-build-one-unit: Delegate each unit with file paths, the data shape, and success criteria, and verify it before the next. Port a shared-primitive improvement to every consumer. Commit liberally. (implement, sequence-verifiable-units, laziness-protocol)
6-decide-tests: Decide each new permanent test through the admission gate. (testing-code, test-behavior-not-implementation)
7-verify-on-surface: Run the feature through its real entry point, with the project's verification skill when one exists. Inconclusive or wrong-surface is not a pass. (prove-it-works)
8-check-blast-radius: When the change touches shared state, a wire format, or a public interface, find its safety fact. (blast-radius)
9-interrogate-if-contested: When the design is contested, run interrogate before shipping. (interrogate)
10-independent-review: Give the diff and evidence to an agent that did not write it. (reviewer agent, no-comments)
11-order-commits: Shape the work into small ordered commits before you push them, and stack follow-ups. (sequence-verifiable-units)
12-update-obsolete-docs: Update documentation this change makes obsolete. (implement)
13-publish-draft-pr: Push the final commits and update the draft PR when publication is authorized. (ship-pr)

Reply: what you built, the data shape, what you chose and why, the throughput checkpoint, the entry-point evidence, and open decisions. Use a table for design alternatives.
