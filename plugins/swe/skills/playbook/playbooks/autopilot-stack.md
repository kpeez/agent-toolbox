# autopilot-stack

Applies when: a queue of changes to build and verify with full autonomy, delivered as one linear base-chained stack the operator lands ("stack them, don't ship", "build the stack, I'll land it").

You own the stack, never the landing. Hand the operator one linear stack of base-chained PRs to review and land.

autopilot-full holds except for how verified work leaves. Each tick re-reads both playbooks, and this one wins where they differ. Choose autopilot-full when the PRs are independent and landing authority is granted. Choose autopilot-stack when the operator wants review before landing, the work is sequenced or coupled, or merge authority is withheld.

1-run-owners-minus-landing: Run autopilot-full's owners, minus the landing. Owners report STACK-READY in place of merge-ready. They never rebase onto another branch, trunk included, and never retarget, merge, close a PR, or arm auto-merge. An item that depends on another branches from that item's branch. (autopilot-full)
2-single-topology-writer: Owners push only their own branches and report each tip and its intended parent. Only you rebase or retarget a link. Append each clean PR in dependency order, with its base set to its parent's branch by `gh pr edit <pr> --base <parent-branch>`. An owner takes your push as its new base and lease, and on a conflict resolves its own slice for you to push. (ship-pr)
3-absorb-drift-at-root: Until landing starts, apply autopilot-full's merge-prep test to each link and rebase the chain bottom-up where it calls for one. Then apply the patch-id rule link by link, since a link's base is its parent. (ship-stack)
4-deliver-chain-hands-off: Each link carries its verdict in its PR. Once landing starts, nobody writes to the chain except the post-merge retarget that ship-stack allows. A mid-landing problem goes through you to the operator, and any fix waits for the operator's go. (ship-stack)

Reply: catch the operator up, with links to the stack root and tip, a one-line verdict per link, and anything parked or excluded with the reason. (ketchup)
