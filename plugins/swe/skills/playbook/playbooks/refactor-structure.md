# refactor-structure

Applies when: change structure, keep behavior.

1-pin-behavior: Pin current behavior with an existing test, a disposable probe, or an equivalence check. (testing-code)
2-name-target-shape: Name the target shape and the reader load it removes. (codebase-design, model-the-domain, minimize-reader-load)
3-subtract-first: Delete dead code and needless layers before adding structure. (subtract-before-adding)
4-move-in-small-steps: Move in small steps that each pass the pin; script repeated moves. (sequence-verifiable-units, build-the-lever)
5-migrate-then-delete: Move every caller, then delete the old path and tests that protect only it. (migrate-callers-then-delete)
6-prove-equivalence: Run the pin again on the real surface, with the project's verification skill when one exists. (verify-on-real-surface)
7-confirm-reader-gain: Revert if reader load did not fall. (minimize-reader-load)
8-independent-review: Give the diff and evidence to an agent that did not write it. (reviewer agent)
9-update-obsolete-docs: Update documentation this change makes obsolete. (implement)
10-publish-draft-pr: Push the final commits and update the draft PR when publication is authorized. (ship-pr)

Reply: old and new shape, the pin, and the equivalence evidence.
