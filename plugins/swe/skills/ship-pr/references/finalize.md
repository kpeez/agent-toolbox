# Finalize a draft pull request

Use this reference only for an explicit `/ship-pr finalize` request. Finalize
means making an existing draft ready for review; it does not mean merging or
deploying.

1. Locate the pull request for the current branch and resolve its linked work
   from explicit evidence. Stop if none exists.
2. Account for pending authorized local changes through the default
   [`/ship-pr`](../SKILL.md) workflow.
3. Re-run applicable repository checks and behavior-specific evidence. Stop on
   a required failure.
4. Mark the draft ready.
5. When authorized, update linked tracker tasks to awaiting review and the spec
   lifecycle to `review`. Do not mark tasks delivered or the spec done solely
   because the pull request is ready.
6. Report the pull request, verification, and state changes.
