# autopilot-stack

Applies when: a queue of PRs to build and verify with full autonomy, handed to the operator to land ("autopilot, don't merge", "stack them, don't ship", "build the stack, I'll land it"). PRs that depend on each other come here also when the user wants them merged. Landing them is a later ship-stack request.

Run autopilot-full, but do not merge. Every loop tick re-reads this file, so each tick sees the no-merge rule.

1-stop-at-verified: In place of autopilot-full step 8, stop when each PR is verified and green at its current head, then hand the PRs to the operator. After the handoff, nobody pushes without the operator's go. (autopilot-full)
2-stack-only-on-dependency: A PR stacks only when it depends on another PR, and stacks stay shallow. This is the one exception to autopilot-full step 5. Subagents commit in their own worktrees and never push or open PRs. The coordinator rebases the unpushed branches into one line (root onto trunk, each child onto its parent branch), verifies the top branch, and runs one `gh stack link` (then updates and checks each PR body with `gh pr edit <n> --body-file <rendered>` and `pr_body.py check -`). Fall back to plain `gh pr create --draft --base <parent-branch>` only when `gh stack` is unavailable. A new head on a lower PR restacks the PRs above it, and a PR whose `git patch-id` the restack leaves unchanged keeps its verdict. (ship-pr, ship-stack)

Reply: as autopilot-full, but list each PR with its verdict in place of what merged. (ketchup)
