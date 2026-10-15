# improve-performance

Applies when: a measured slowness to improve against a baseline.

You own the measurement story. Plan, review, verify the numbers.

Tie every fix to a measurement. Do not read source instead of measuring. The performance mantras, cheapest first, are these. Do not do it, and stop work whose result nothing uses. Do it, but do not do it again. Do it less. Do it later. Do it when they are not looking. Do it concurrently. Do it cheaper. For sustained improvement of one metric, use hillclimb-metric.

1-measure-baseline: Capture a baseline trace on the real surface, with run count and spread, before any change. Vet it with benchmark-checklist. (diagnose, benchmark-checklist, explain-the-number)
2-ground-hypotheses: Run how over the slow path. Do not claim a ceiling you have not run. (how)
3-name-limiter: Name the limiting resource with profiling evidence. (explain-the-number)
4-try-mantras: Try the mantras in order and stop at the first that meets the target.
5-plan-fix: When the fix crosses a function boundary, run architect first. Give the code delegate a specific scope and review its diff. (architect, implement)
6-change-one-thing: Change one thing at a time, capture a post-fix trace, and verify each attempt before the next. (sequence-verifiable-units)
7-compare-artifacts: Parse and compare the baseline and post-fix artifacts, such as JSON loaded into sqlite. Inconclusive or wrong-surface is not a pass. (benchmark-checklist, explain-the-number)
8-explain-the-gain: Explain the gain and why it is not larger. (explain-the-number)
9-verify-behavior-unchanged: Show behavior is unchanged on the real surface, with the project's verification skill when one exists. (prove-it-works)
10-update-obsolete-docs: Update documentation this change makes obsolete. (implement)
11-publish-draft-pr: Cite the measurement in the PR, push the final commits, and update the draft PR when publication is authorized. (ship-pr)

Reply: baseline, post-fix number, delta, spread, limiter, and artifact path.
