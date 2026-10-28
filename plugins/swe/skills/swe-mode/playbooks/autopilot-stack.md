# autopilot-stack

Applies when: a queue of PRs to build and verify with full autonomy, handed to the operator to land ("autopilot, don't merge", "stack them, don't ship", "build the stack, I'll land it").

Run autopilot-full, but do not merge. Every loop tick re-reads this file, so each tick sees the no-merge rule.

1-stop-at-verified: In place of autopilot-full step 8, stop when each PR is verified and green at its current head, then hand the PRs to the operator. After the handoff, nobody pushes without the operator's go. (autopilot-full)
2-stack-only-on-dependency: A PR stacks only when it builds on another PR. This is the one exception to autopilot-full step 5. Base that PR on the other PR's branch in place of trunk. In place of the rebase onto trunk, each PR rebases onto its parent PR's branch, and the stack root rebases onto trunk. A new head on a lower PR restacks the PRs above it, and a PR whose `git patch-id` the restack leaves unchanged keeps its verdict. (ship-pr, ship-stack)

Reply: as autopilot-full, but list each PR with its verdict in place of what merged. (ketchup)
