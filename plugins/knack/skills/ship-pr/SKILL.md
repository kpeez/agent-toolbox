---
name: ship-pr
description: Publish branch work. Default — group the current branch diff into atomic commits, push, and open a draft PR if missing. `/ship-pr finalize` — re-verify and flip the draft PR to ready for review.
---

# /ship-pr — Group, Commit, Push, Draft PR

Bundle the committed + uncommitted changes on the current branch into atomic
commits, push, and ensure a draft PR exists.

Two modes:

- **Default** (`/ship-pr [spec]`) — the workflow below: verify, group, commit,
  push, draft PR.
- **Finalize** (`/ship-pr finalize`) — closing step, see
  [Finalize](#finalize-ship-pr-finalize). Merging stays a human action.

## Rules

- **Atomic commits.** Imperative, informative subjects. One coherent intent per commit —
  never mixed — ordered so each commit leaves the tree buildable.
- **PR title and body come from NNNN-<slug>.md, linked tracker issues, and the diff.**
- **Never add agent attribution** (`Co-authored-by`, `Generated with`, etc.).
- **Draft PRs by default.** Never flip an existing PR's draft/ready state; mark
  ready only in finalize mode or when the user asks.
- **Never force-push.** Squash merge by default.
- **Reviewable Markdown.** PR bodies and optional PR markdown artifacts must be
  easy to review as plain Markdown.
- **Verify before you commit.** Lint, types, and tests (including the tests
  named in the spec's Verification section) must pass first; a failing check is
  a stop, not a warning.

## Workflow

1. **Context** — resolve the spec: the argument if given, else the most
   recently modified `docs/agents/specs/NNNN-*.md`, else proceed without one. Read
   the spec and its linked tracker issues for intent and the desired PR slice.
   Resolve the base branch from the remote default — never assume `main`:
   `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`, else
   `git symbolic-ref --short refs/remotes/origin/HEAD | sed 's@^origin/@@'`,
   else `main`.
2. **Verify** — run the repo's lint, type-check, and tests. If any fail, stop
   and report; do not commit on red.
3. **Group** — collect the diff against `git merge-base <base> HEAD` plus
   uncommitted and untracked work; cluster files (within-file hunks if needed)
   into single-intent groups.
4. **Commit** — stage exactly one group at a time and commit it; check
   `git status` between commits so nothing leaks across groups.
5. **Push** — `git push -u origin HEAD` (plain `git push` if upstream is set).
6. **Draft PR** — if none exists, `gh pr create --draft --base <base>`; if one
   exists, leave its state alone.
7. **Link** — comment the PR URL on the tracker issue(s) and move them toward
   review. Task state lives on the tracker, not in local files.
8. **Mark the spec** — if a spec was resolved in step 1, set its `status: review`;
   the code now exists and is being proven. Set `blocked: true` with a
   `blocked_reason` instead if verification is stuck on something external.
9. **Summarize** — branch, base, commit list (sha + subject), PR URL, tracker
   issues touched.

## Finalize (`/ship-pr finalize`)

Flip the branch's draft PR to ready for review. Merging is not part of this
skill — it stays a human action.

1. **Locate** — `gh pr view` for the current branch; stop and report if no PR
   exists (run the default mode first). Resolve the spec as in default step 1,
   else from the `<!-- knack-spec: <repo>/<slug> -->` marker on the tracker
   parent of the PR's linked issue(s); proceed without one if nothing resolves.
2. **Sync** — ensure the local branch is pushed; commit and push any pending
   work via the default workflow first.
3. **Verify** — re-run lint, types, and tests (including the spec's
   Verification tests). Any failure is a stop, not a warning.
4. **Ready** — `gh pr ready <number>`.
5. **Link** — comment on the tracker issue(s) and move them to review/done per
   the tracker's states.
6. **Close the spec** — if a spec was resolved in step 1 and its parent's
   remaining children are closed, set `status: done`: bump `updated`, preserve
   `created`, and append yourself to `authors` if the spec carries them — never
   remove a prior author. This is the step nothing else can do for you: a merged
   PR does not know which spec it completed. No spec, or slices still open —
   leave the status alone and say so in the summary.
7. **Summarize** — PR URL, verification results, tracker issues touched, spec
   status.

## Markdown artifact (on request only)

When the user asks, or as a fallback when `gh` is unavailable: write
`docs/agents/specs/NNNN-<slug>-pr.md` (gitignored — never committed) with one
section per commit: subject, one-line rationale, file list, and the
`git diff <base>...HEAD -- <files>` output for that group.
