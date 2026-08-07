---
name: ship-pr
description: Publish branch work as atomic commits, a push, and a draft PR. Use when the user runs /ship-pr, or proactively when branch changes reach a stable verified state (lint, types, tests green) with no more edits in flight — commit and keep a draft PR current without being asked. `/ship-pr finalize` (user-triggered only) re-verifies and flips the draft PR to ready for review.
---

# /ship-pr — Group, Commit, Push, Draft PR

Bundle the committed + uncommitted changes on the current branch into atomic
commits, push, and ensure a draft PR exists.

Two modes:

- **Default** (`/ship-pr [spec]`) — the workflow below: verify, group, commit,
  push, draft PR. May run **quasi-autonomously**: when the work on the branch
  reaches a stable verified state, run this mode without being asked. Its
  outputs are all reversible or draft-gated — commits on a branch, a push, a
  draft PR — so autonomous invocation is safe; flipping to ready is not part
  of it.
- **Finalize** (`/ship-pr finalize`) — closing step, see
  [Finalize](#finalize-ship-pr-finalize). Only the user triggers this mode.
  Merging stays a human action.

## Rules

- **Atomic commits.** Imperative, informative subjects. One coherent intent per commit —
  never mixed — ordered so each commit leaves the tree buildable.
- **PR title and body come from NNNN-<slug>.md, linked tracker issues, and the
  diff** — shaped per [PR body](#pr-body) below.
- **No tracker leakage.** PR bodies, titles, and commit messages are
  self-contained technical text — never include tracker URLs, issue quotes, or
  workflow/process chatter. The PR link lives on the tracker side (private may
  reference public, never the reverse). A bare issue id in the branch name is
  the only tracker trace GitHub sees.
- **Tracker-linking branch names.** When the tracker is Linear, the branch (at
  creation, before first push) is named `<user>/<issue-id>-<slug>` (e.g.
  `kyle/kp-123-fix-auth`) so Linear's GitHub integration links the PR and
  automates the In Review/Done transitions.
- **Never add agent attribution.** No `Co-authored-by` trailer naming Claude or
  Anthropic, no `Generated with …` footer, no 🤖, and above all **no session
  URL** — a `claude.ai`/`claude.com` link in a commit message is unrewritable
  once pushed. The `block-agent-attribution` hook rejects the commit or
  `gh` call outright; when it fires, rewrite the text rather than working
  around the guard.
- **Draft PRs by default.** Never flip an existing PR's draft/ready state; mark
  ready only in finalize mode or when the user asks.
- **Never force-push.** Squash merge by default.
- **Reviewable Markdown.** PR bodies and optional PR markdown artifacts must be
  easy to review as plain Markdown.
- **Verify before you commit.** Lint, types, and tests (including the tests
  named in the spec's Verification section) must pass first; a failing check is
  a stop, not a warning.

## PR body

Written for a reviewer with no session context. Three parts:

- **What & why** — the problem, what changed, and why this approach. One or two
  short paragraphs of self-contained technical text; no process narration.
- **Reviewer's guide** — how to read the diff: the load-bearing change first,
  a suggested commit-by-commit order, and which parts are mechanical noise
  (renames, generated files, formatting).
- **Verification** — behavioral evidence, not gate status. **Never list
  lint/type-check/test-suite runs as verification** — those are global
  blockers; passing them is the price of admission, not proof of anything.
  Instead demonstrate the stated goals working:
  - a reproducible command a reviewer can paste, with the actual observed
    output (or a before → after comparison);
  - the specific committed tests that pin each goal, by name — not "pytest
    passed";
  - known gaps and pre-existing failures, stated explicitly.

  If you cannot produce a single reproducible demonstration of the change,
  say so and explain what a reviewer should look at instead — don't pad the
  section with gate output.

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
   review. Task state lives on the tracker, not in local files. If Linear's
   GitHub integration already attached the PR and moved the issue (via the
   branch name), verify instead of duplicating.
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
   else by matching the tracker container of the PR's linked issue(s) against
   the `tracker_container` recorded in each spec's frontmatter; proceed without
   one if nothing resolves.
2. **Sync** — ensure the local branch is pushed; commit and push any pending
   work via the default workflow first.
3. **Verify** — re-run lint, types, and tests (including the spec's
   Verification tests). Any failure is a stop, not a warning.
4. **Ready** — `gh pr ready <number>`.
5. **Link** — comment on the tracker issue(s) and move them to review/done per
   the tracker's states.
6. **Close the spec** — if a spec was resolved in step 1 and its container's
   remaining slices are closed, set `status: done`: bump `updated`, preserve
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
