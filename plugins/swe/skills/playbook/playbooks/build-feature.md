# build-feature

Applies when: new or changed behavior.

You own the design. Plan, review, verify.

Delegate implementation and stay in the lead. Delegation is mandatory and the laziness protocol does not waive it, because the gain is review separation. A subagent that cannot spawn owns the diff directly and keeps the same review separation. Code-coupled work goes to one owner with the checkpoint inline, and that owner fans out after the blocking phase. Parent-level fan-out is for slices with independent artifacts. Rewrite the checkpoint at phase boundaries. Spawn a fresh owner rather than chaining interrupts.

1-map-subsystem: Run how over the affected subsystem. (how)
2-interview-on-open-decisions: When scope or behavior rests on a product or preference decision the user has not made, run interview-user on those decisions only. Settle facts a run can show by prototype instead. (interview-user, build-prototype)
3-name-data-shape: Name the data shape, its states, their owners, and its organizing structure before logic. Prefer a state machine to scattered booleans and a table to branching. (model-the-domain, foundational-thinking)
4-explore-designs: When the code crosses a function boundary, run architect for parallel design exploration. For a consequential interface, map callers, invariants, and errors. (architect, codebase-design, redesign-from-first-principles)
5-write-throughput-checkpoint: Add four task items for blocking first steps, independent workstreams, shared mutable state, and the smallest safe decomposition. Mark one that does not apply `n/a: <reason>`. (separate-before-serializing-shared-state)
6-build-one-unit: Delegate each unit with file paths, the data shape, and success criteria, and verify it before the next. Port a shared-primitive improvement to every consumer. Commit liberally. (implement, sequence-verifiable-units, laziness-protocol)
7-decide-tests: Decide each new permanent test through the admission gate. (testing-code, test-behavior-not-implementation)
8-verify-on-surface: Run the feature through its real entry point, with the project's verification skill when one exists. Inconclusive or wrong-surface is not a pass. (prove-it-works)
9-check-blast-radius: When the change touches shared state, a wire format, or a public interface, find its safety fact. (blast-radius)
10-review-if-contested: When the design is contested, give the design and its evidence to a reviewer agent before shipping. (reviewer agent)
11-independent-review: Give the diff and evidence to an agent that did not write it. (reviewer agent, no-comments)
12-order-commits: Shape the work into small ordered commits before you push them, and stack follow-ups. (sequence-verifiable-units)
13-update-obsolete-docs: Update documentation this change makes obsolete. (implement)
14-publish-draft-pr: Push the final commits and update the draft PR when publication is authorized. (ship-pr)

Reply: what you built, the data shape, what you chose and why, the throughput checkpoint, the entry-point evidence, and open decisions. Use a table for design alternatives, and show the design with the `writing` show-me visuals.
