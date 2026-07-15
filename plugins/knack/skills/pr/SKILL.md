---
name: pr
description: Group current branch diff into atomic commits, push, and open a draft PR if missing. Use when ready to publish branch work.
model: sonnet
---

# /pr — Group, Commit, Push, Draft PR

Bundle the committed + uncommitted changes on the current branch into atomic
commits, push, and ensure a draft PR exists.

## Rules

- **Atomic commits.** Imperative, informative subjects. One coherent intent per commit —
  never mixed — ordered so each commit leaves the tree buildable.
- **PR title and body come from SPEC.md, linked tracker issues, and the diff.**
- **Never add agent attribution** (`Co-authored-by`, `Generated with`, etc.).
- **Draft PRs by default.** Never flip an existing PR's draft/ready state; mark
  ready only when the user asks.
- **Never force-push.** Squash merge by default.
- **Reviewable Markdown.** Use the `documentation` skill when drafting PR bodies
  or optional PR markdown artifacts.
- **Verify before you commit.** Lint, types, tests, and spec examples must pass
  first; a failing check is a stop, not a warning.

## Workflow

1. **Context** — resolve `<feature>`: the argument if given, else the most
   recently modified `specs/<feature>/SPEC.md`, else proceed without one. Read
   the spec and its linked tracker issues for intent and the desired PR slice.
   Resolve the base branch from the remote default — never assume `main`:
   `gh repo view --json defaultBranchRef -q .defaultBranchRef.name`, else
   `git symbolic-ref --short refs/remotes/origin/HEAD | sed 's@^origin/@@'`,
   else `main`.
2. **Verify** — run the repo's lint, type-check, tests, and spec examples. If any
   fail, stop and report; do not commit on red.
3. **Group** — collect the diff against `git merge-base <base> HEAD` plus
   uncommitted and untracked work; cluster files (within-file hunks if needed)
   into single-intent groups.
4. **Commit** — stage exactly one group at a time and commit it; check
   `git status` between commits so nothing leaks across groups.
5. **Push** — `git push -u origin HEAD` (plain `git push` if upstream is set).
6. **Draft PR** — if none exists, `gh pr create --draft --base <base>`; if one
   exists, leave its state alone.
7. **Link** — comment the PR URL on the tracker issue(s) and move them toward
   review. Status lives on the tracker, not in local files.
8. **Summarize** — branch, base, commit list (sha + subject), PR URL, tracker
   issues touched.

## Markdown artifact (on request only)

When the user asks, or as a fallback when `gh` is unavailable: write
`specs/<feature>/pr-<issue-slug>.md` (gitignored — never committed) with one
section per commit: subject, one-line rationale, file list, and the
`git diff <base>...HEAD -- <files>` output for that group.
