# run-autonomously

Applies when: a long task to drive to completion without stopping ("run until done", "/loop until X", "going to bed, keep going").

You own the exit condition. Define done, then drive to it without stopping.

1-state-exit-predicate: Before the first iteration, state the exit condition as a checkable predicate, such as tests green, the repro fixed, all N PRs merged, or a pixel diff of zero.
2-pick-wake-mechanism: In Claude Code, use `/loop`. An event to watch (CI, a merge, a ref that moves) gets a background watcher, such as `gh pr checks <pr> --watch`, with a long heartbeat as the fallback. No event gets a fixed-interval heartbeat sized to when the result is worth a re-check. In Codex, say that the user reruns the task by hand.
3-open-decision-log: Open the decision log before the first iteration. (log-decisions)
4-iterate-smallest-change: Each iteration makes the smallest change the evidence justifies, verifies it against the predicate, commits it when it advanced, and discards it when it did not. Revert a "might help" extra instead of letting it ride. Verify each unit before the next. (sequence-verifiable-units, prove-it-works)
5-own-mid-run-discoveries: Fix broken skills, related bugs, flaky verifiers, review noise, tooling failures, and fixable drift yourself, each out-of-band fix in its own PR. Do not park reversible work for the human. Surface only irreversible actions, product calls no experiment can settle, or a real dead end. Return to the predicate after each side fix. (never-block-on-the-human)
6-log-each-iteration: Write a row per iteration with what changed and whether the predicate moved. (log-decisions)
7-stop-on-predicate: Stop when the predicate holds. A plateau is not a stop, so pivot the approach and push past it. Surface a genuine dead end instead of spinning. Never relax the predicate to declare victory.
8-publish-draft-pr: Push the final commits and update the draft PR when publication is authorized. (ship-pr)

Reply: the exit condition, iterations run, what landed, what was discarded, the final predicate state, and the decision log path.
