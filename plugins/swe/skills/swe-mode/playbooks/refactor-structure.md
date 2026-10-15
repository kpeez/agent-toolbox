# refactor-structure

Applies when: change structure, keep behavior.

You own the contract. The structure changes. The behavior does not.

When the cleanup reveals a missing feature or a real bug, split it out and ship the structural change first against the pinned contract. A named redesign routes to build-feature. Large or cross-cutting structural work goes to figure-it-out.

1-pin-behavior: Run how to learn the contract, then pin it with a characterization test, snapshot, or equivalence harness before any structure moves. Type check and lint are not a pin. (how, testing-code)
2-name-missing-structure: Name the structure the code is missing. The reshape must delete branches or invalid states, not add indirection. Boring code stays when its shape is clear and local. (model-the-domain)
3-name-target-shape: State the module layout, types, and call graph as if built today. When the target crosses a function boundary, run architect first. When the target shape rests on a product or preference decision the user has not made, run interview-user on those decisions only. (foundational-thinking, redesign-from-first-principles, architect, codebase-design, interview-user)
4-subtract-first: Delete dead code, one-caller wrappers, redundant validators, and orphan references before adding structure. Revert a speculative cleanup. (subtract-before-you-add, laziness-protocol)
5-move-in-small-steps: Move in steps that each keep the pin green, and script repeated moves. Spot-check every rename in strings, prose, and back-references. (sequence-verifiable-units, build-the-lever)
6-migrate-then-delete: Move every caller and delete the old API in the same wave. No shims and no parallel old and new paths. (migrate-callers-then-delete-legacy-apis)
7-prove-equivalence: Run the pin again on the real surface, with the project's verification skill when one exists. For a larger reshape, diff old and new outputs or replay a recorded baseline. (prove-it-works)
8-confirm-reader-gain: Revert if reader load did not fall. (minimize-reader-load)
9-independent-review: Give the diff and evidence to an agent that did not write it. (reviewer agent, no-comments)
10-order-commits: Order the commits as subtraction, then reshape, then follow-on cleanup, each green. (sequence-verifiable-units)
11-update-obsolete-docs: Update documentation this change makes obsolete. (implement)
12-publish-draft-pr: Push the final commits and update the draft PR when publication is authorized. (ship-pr)

Reply: old and new shape, the pin, the equivalence evidence, the reader-load delta, and what shipped and what was reverted. No new behavior.
