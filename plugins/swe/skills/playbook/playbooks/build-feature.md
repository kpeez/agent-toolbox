# build-feature

Applies when: new or changed behavior.

1-name-data-shape: Name the data shape, its states, and their owners before logic. (model-the-domain)
2-design-interface: For a consequential new interface, map callers and state invariants and errors. (codebase-design)
3-plan-throughput: List blocking steps, independent workstreams, shared state, and the smallest safe split. (orchestrate, separate-shared-state)
4-build-one-unit: Build one unit at a time with the smallest change and verify it before the next. (implement, sequence-verifiable-units)
5-decide-tests: Decide each new permanent test through the admission gate. (testing-code)
6-verify-on-surface: Run the feature through its real entry point, with the project's verification skill when one exists, and record the verdict. (verify-on-real-surface)
7-check-blast-radius: When the change touches shared state, a wire format, or a public interface, find its safety fact. (blast-radius)
8-independent-review: Give the diff and evidence to an agent that did not write it. (reviewer agent)
9-update-obsolete-docs: Update documentation this change makes obsolete. (implement)
10-publish-draft-pr: Push the final commits and update the draft PR when publication is authorized. (ship-pr)

Reply: what changed, the data shape, and the entry-point evidence.
