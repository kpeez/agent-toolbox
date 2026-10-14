# CI checks

Read this reference to watch checks and to classify a failed check. `<pr>` is
the pull-request number, `<base>` its base branch, and `<head-sha>` the current
head commit (`gh pr view <pr> --json headRefOid,baseRefName`).

## Watch checks

Watch checks with `gh pr checks <pr> --watch --fail-fast --required`. Exit 0
means all listed checks passed, 8 means pending, and 1 means a failure or no
checks. Read the output to tell the last two apart. GitHub registers checks
some time after a push, so "no checks reported" can come too early. The
repository runs no CI only when both of these hold:

- "No checks reported" still holds one minute or more after the last push or
  branch update.
- `gh run list --limit 1 --json databaseId` prints `[]`: the repository has no
  workflow runs.

When workflow runs exist, wait up to ten minutes for checks to appear, then
report the missing checks as a blocker. When `--required` lists nothing but
checks exist, use every check that `gh pr checks <pr>` lists.

## Read pull-request status

The `babysit-pr` playbook and Drive to green read status with these commands.
Re-read them each time a check watch returns.

- Merge state:
  `gh pr view <pr> --json state,isDraft,mergeable,mergeStateStatus,reviewDecision,headRefOid`.
  `mergeable` is `CONFLICTING` on a conflict. `mergeStateStatus` is `BEHIND`
  on a stale base, `BLOCKED` while a required check or approval is missing,
  `DRAFT` on a draft, and `CLEAN` when a ready pull request can merge.
- Unresolved review threads, with the top-level comment id that a reply
  needs:

  ```bash
  gh api graphql -F owner='{owner}' -F repo='{repo}' -F pr=<pr> -f query='
    query($owner: String!, $repo: String!, $pr: Int!) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $pr) {
          reviewThreads(first: 100) {
            nodes { isResolved isOutdated
              comments(first: 1) { nodes { databaseId author { login } path line body } } }
          }
        }
      }
    }' --jq '.data.repository.pullRequest.reviewThreads.nodes[]
      | select(.isResolved | not) | .comments.nodes[0]'
  ```

- Review-bot passes, for the pass count in
  [bot-triage](bot-triage.md):
  `gh api repos/{owner}/{repo}/pulls/<pr>/reviews --jq '[.[] | select(.user.type == "Bot") | .user.login] | group_by(.) | map({bot: .[0], passes: length})'`.

A pull request is merge-ready when all of these hold at the current head:
required checks pass, `mergeable` is `MERGEABLE`, no unresolved review thread
blocks it, and `reviewDecision` is not `CHANGES_REQUESTED`. A draft reads
`DRAFT` here; that is expected, and only Land or Finalize marks it ready. An
owner approval that is still missing is a wait, not a blocker to fix.

## Classify a failed check

Read the failure first. `gh pr checks <pr> --json name,state,link` gives each
check's link; the run id is the number after `/runs/`.
`gh run view <run-id> --log-failed` gives the failed steps. Then
give the failure exactly one class:

- `in-diff`: the failure is in code, tests, or config that this branch
  changes. Only this class earns a fix commit.
- `outside-diff`: the failure is in code the branch does not touch. Spend no
  rerun. Check two causes and report the one you find:
  - Stale base: `git fetch origin <base>`, then
    `git merge-base --is-ancestor origin/<base> HEAD`. Exit 1 means the
    branch is behind. Update it with `gh pr update-branch <pr>`, which merges
    the base into the branch without force. Run it only when
    `git rev-parse HEAD` equals the PR head, so push local fix commits first
    (Drive to green `4-push-one-wave`, or Publish `4-push`). Then run
    `git pull --ff-only`. The head changes, so when a verdict record exists,
    redo Land `3-recheck-before-landing`.
  - Red trunk: `gh run list --branch <base> --limit 5`. A failure on the base
    branch is not this branch's to fix. Report it.
- `flake-or-infra`: the log shows a runner, network, or service fault, or a
  test that fails without a code cause. It earns exactly one fresh run of the
  whole workflow: `gh run rerun <run-id>`, without `--failed` or `--job`.

An identical failure on that one rerun is not flake. Read
`gh run view <run-id> --log-failed` again and reclassify.
