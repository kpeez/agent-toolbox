# land-verified-pr

Applies when: mark ready and merge a verified PR.

1-get-independent-verdict: Brief an agent that did not write the code to return PASS, PASS+NOTES, or FAIL with head SHA. (reviewer agent, ci-and-landing)
2-key-verdict-to-patch: Record head SHA, base SHA, and patch-id with the verdict in the PR body's Evidence section. (ci-and-landing)
3-recheck-before-landing: Recompute the patch-id and re-verify when it changed. (ci-and-landing)
4-mark-ready-and-merge: Mark ready and merge only under the Ready and Merge conditions of the ci-and-landing skill. (ci-and-landing)

Reply: verdict, patch-id, and landing state.
