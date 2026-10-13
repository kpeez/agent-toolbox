# Finalize a draft pull request

Use this reference only for an explicit `/ship-pr finalize` request. Finalize
makes an existing draft ready for review. It merges only under the merge rule
in [`/ship-pr`](../SKILL.md), and it never deploys.

1. Locate the pull request for the current branch and resolve its linked work
   from explicit evidence. Stop if none exists.
2. Account for pending authorized local changes through the default
   [`/ship-pr`](../SKILL.md) workflow.
3. Re-run applicable repository checks and behavior-specific evidence. Stop on
   a required failure.
4. Mark the draft ready.
5. When the merge rule authorizes a merge, land the pull request through the
   Land steps of [ci-and-landing](../../ci-and-landing/SKILL.md). Otherwise
   stop at ready and say which condition is missing.
6. Leave issue status to the tracker's GitHub integration; a ready pull request
   does not mark work delivered.
7. Report the pull request, verification, and state changes.
