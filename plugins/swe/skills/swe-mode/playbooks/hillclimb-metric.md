# hillclimb-metric

Applies when: sustained improvement of one measurable metric against a target, through a loop of measured attempts with one keep-or-revert decision per attempt.

You own the metric and the experiment's integrity. Supervise and review. Delegate the attempts.

A one-off fix is fix-bug or improve-performance. Here the core discipline is one change, one measurement, keep or revert. Never stack untested changes. Never claim a win from code inspection. Correctness and simplicity outrank the number. For an unattended run, borrow only the wake mechanism of run-autonomously, not its stop rule.

1-ground-workload: Trace the target and name the workload dimensions that move the result. Select a case that reproduces the user's complaint. If none does, fix the repro first.
2-fix-metric-and-stop: Fix one metric, its better direction, and a stop predicate that pairs a target with a floor on attempts. Use the user's numbers or agree them.
3-freeze-harness: Prove the harness separates contrasting workloads, vet it, and make it print its error count and work count. Freeze one command that reports a median of N. Record the baseline and a green regression gate. (build-the-lever, benchmark-checklist)
4-open-decision-log: Keep a gitignored `decision.tsv` with id, hypothesis, change, before, after, delta, tests, verdict, and note. Give each attempt a new id, a crash or a retry included, and never reuse one. Read the log before each attempt. (log-decisions)
5-ground-each-hypothesis: Name a specific mechanism for each hypothesis. For a perf metric, order hypotheses by the performance mantras, but not their stop rule. (improve-performance)
6-delegate-attempt: Give one hypothesis to a code subagent with a tight scope and review its diff. Run independent hypotheses in parallel worktrees. (guard-the-context-window, separate-before-serializing-shared-state)
7-measure-and-decide: Measure before and after with the frozen harness and run the gate. Keep a change only when the metric moves past noise and the gate stays green. Otherwise revert it in full. (prove-it-works, explain-the-number, sequence-verifiable-units)
8-commit-and-log: Commit each kept fix alone, staging only its files with `git add <files>`, never `-A`. Log the row whether kept, reverted, or crashed. (log-decisions)
9-push-past-plateau: After several rejects in a row, pivot category, combine near-misses, re-read the source, or try something more radical. Revert a win that breaks behavior. Keep a simplification that holds the number. (laziness-protocol)
10-stop-on-predicate: Stop when the predicate holds or the remaining ideas are not worth their cost. Do not relax the predicate or quit with cheap ideas untried. When stuck, say so instead of spinning.
11-publish-draft-pr: When publication is authorized, push the kept commits in landing order and update the draft PR. (ship-pr)

Reply: the metric and target, baseline to final with percent delta, iterations kept and reverted, each kept fix on one line, the `decision.tsv` path, and the next idea you would try.
