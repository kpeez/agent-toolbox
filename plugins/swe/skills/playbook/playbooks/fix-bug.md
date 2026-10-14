# fix-bug

Applies when: a reported defect to reproduce, root-cause, and fix.

You own this task. Plan, review, verify.

Delegate the investigation and the fix to subagents and stay in the lead. Be scientific. Every shipped line traces to runtime evidence. A change that "might help" is a hypothesis, not a fix, and it does not ship. When evidence refutes a hypothesis, revert what it motivated.

1-reproduce-failure: Reproduce it yourself on the reported surface, with the project's verification skill when one exists. Ask the user only with a specific reason that surface cannot reach it. If it does not fire, synthesize the trigger, tighten conditions, or instrument until it does. (diagnose, prove-it-works)
2-binary-search-cause: Seed hypotheses with how and why. Each pass, take the split that cuts the most problem space, get runtime evidence, and eliminate. Instrument when state is unclear. Do not guess. (how, why, diagnose, fix-root-causes)
3-confirm-mechanism: Confirm the surviving mechanism with runtime evidence before you plan the fix. When two fixes on one premise have failed, question the premise. (fix-root-causes, attack-the-premise)
4-sweep-for-pattern: Search for other instances of the same faulty pattern. (fix-root-causes)
5-plan-fix: When the fix crosses a function boundary, run architect first. Give the code delegate a specific scope. (architect, implement)
6-decide-regression-test: Decide through the admission gate whether the reproduction becomes a permanent test. (testing-code, test-behavior-not-implementation)
7-commit-failing-repro: When the bug has a cheap local test path, commit the failing repro before the fix. Skip when the test is expensive, integration-heavy, or unclear. (testing-code, sequence-verifiable-units)
8-apply-smallest-fix: Apply the smallest fix the evidence justifies, nothing more. (implement, subtract-before-you-add, laziness-protocol)
9-verify-original-repro: Run the original reproduction again on the same surface. Inconclusive or wrong-surface is not a pass. Unit tests show branch behavior, not bug absence. (prove-it-works)
10-check-blast-radius: When the change touches shared state, a wire format, or a public interface, find its safety fact. (blast-radius)
11-clean-the-diff: Self-review the diff and keep a comment only for a non-obvious why. (no-comments, unslop)
12-update-obsolete-docs: Update documentation this change makes obsolete. (implement)
13-publish-draft-pr: Push the final commits and update the draft PR when publication is authorized. (ship-pr)

Reply: what broke, the root cause, the fix, how you verified it, and the failing-then-passing repro output verbatim.
