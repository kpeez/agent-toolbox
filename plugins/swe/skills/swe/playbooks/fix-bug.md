# fix-bug

Applies when: a reported defect to reproduce, root-cause, and fix.

1-reproduce-failure: Reproduce the failure on the surface where it was reported. (diagnose)
2-find-root-cause: Find the root cause from ranked hypotheses and runtime evidence, not guesses. (diagnose, fix-root-causes)
3-sweep-for-pattern: Search for other instances of the same faulty pattern. (fix-root-causes)
4-decide-regression-test: Decide through the admission gate whether the reproduction becomes a permanent test. (testing-code)
5-apply-smallest-fix: Apply the smallest fix the evidence justifies. (implement, subtract-before-adding)
6-verify-original-repro: Run the original reproduction again on the same surface. (verify-on-real-surface)
7-check-blast-radius: When the change touches shared state, a wire format, or a public interface, find its safety fact. (blast-radius)
8-update-obsolete-docs: Update documentation this change makes obsolete. (implement)
9-publish-draft-pr: Push the final commits and update the draft PR when publication is authorized. (ship-pr)

Reply: what broke, the root cause, the fix, and the failing-then-passing evidence verbatim.
