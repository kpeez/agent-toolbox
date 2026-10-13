# Finalize a draft pull request

Use this reference only for an explicit `/ship-pr finalize` request. Finalize
makes an existing draft ready for review, and it never deploys.

1. Locate the pull request for the current branch and resolve its linked work
   from explicit evidence. Stop if none exists.
2. Account for pending authorized local changes through the default
   [`/ship-pr`](../SKILL.md) workflow.
3. Re-run applicable repository checks and behavior-specific evidence. Stop on
   a required failure.
4. When the current request or the user's standing instructions call for a
   merge, run the Land steps of
   [ci-and-landing](../../ci-and-landing/SKILL.md). They mark the draft ready
   and merge only when their conditions hold. Otherwise mark the draft ready.
5. Leave issue status to the tracker's GitHub integration; a ready pull request
   does not mark work delivered.
6. Report the pull request, verification, and state changes.
