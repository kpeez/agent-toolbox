# ship-stack

Applies when: the user asks to land, ship, or merge a green PR or stack.

You own what lands. Verify each PR independently, land only the verified run from the root, then keep your hands off the stack.

This playbook runs only on an explicit request to land or ship. It begins where babysit-pr ends. The Land procedure of ship-pr governs each merge, its merge authority, and its release effects. Use `gh` only. Green CI and an approving bot review are not verdicts, because neither runs the change as a user would.

1-verify-each-pr: Give each PR its own verifier, an agent that did not write the code. It runs the change the way a user would, parent against head, with the project's verification skill when one exists, and records `PASS`, `PASS+NOTES`, or `FAIL` on that PR keyed to the patch-id. (ship-pr, reviewer agent, prove-it-works)
2-find-verified-run: Walk up from the lowest unmerged PR and stop at the first without `PASS` or `PASS+NOTES`. The PRs below it are the run, and the top one is the ceiling. A verified PR above an unverified one waits. One whose branch neither holds nor needs that code may move onto trunk and land alone after a fresh verdict.
3-recheck-patch-ids: Compare `git patch-id` at the verdict SHA with the current head before you trust an older verdict, since a chain rebase moves every PR above it. When only tests, docs, or lint config differ, a lane's result stands if what it ran builds the same at both SHAs apart from noise. Report each kind of noise with its files. Rerun a lane with no build output, and re-verify anything else that drifted. (ship-pr)
4-land-bottom-up: Merge the run's lowest unmerged PR with `gh pr merge <pr> --squash --match-head-commit <sha>`, or the repository's merge method. Read it back with `gh pr view <pr> --json state,mergedAt,baseRefName`, since a queued PR or an armed auto-merge is not a merge. Then retarget the next PR to trunk with `gh pr edit <pr> --base <trunk>`, move its patch onto the merge result, push with `--force-with-lease`, and merge it once its checks pass and its verdict survives step 3. (ship-pr)
5-hands-off-while-landing: Make no change to a branch or base except step 4's move of the next PR. Arm `--auto` only on a PR whose verdict covers its current head. Watch with `gh pr checks <pr> --watch` and re-read `gh pr view` each time it returns, until the ceiling reads merged. A base that moves to trunk when its parent merges is expected. When a merge stalls, find out why before you change anything.
6-stop-at-ceiling: Stop at the ceiling. Extending the run takes new verdicts, so it is a new pass through step 1.

Reply: the verified run and its ceiling, each PR's verdict and who produced it, what landed and how you confirmed it, and what the next gap needs, with PR links.
