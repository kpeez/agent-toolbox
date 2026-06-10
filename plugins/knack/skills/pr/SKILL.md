---
name: pr
description: Group current branch diff into atomic commits, push, and open a draft PR if missing. Use when ready to publish branch work.
model: haiku
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

## Workflow

1. **Context** — resolve `<feature>`: the argument if given, else the most
   recently modified `specs/<feature>/SPEC.md`, else proceed without one. Read
   the spec and its linked tracker issues for intent and the desired PR slice.
2. **Group** — collect the diff against `git merge-base main HEAD` plus
   uncommitted and untracked work; cluster files (within-file hunks if needed)
   into single-intent groups.
3. **Commit** — stage exactly one group at a time and commit it; check
   `git status` between commits so nothing leaks across groups.
4. **Push** — `git push -u origin HEAD` (plain `git push` if upstream is set).
5. **Draft PR** — if none exists, `gh pr create --draft --base main`; if one
   exists, leave its state alone.
6. **Link** — comment the PR URL on the tracker issue(s) and move them toward
   review. Status lives on the tracker, not in local files.
7. **Summarize** — branch, base, commit list (sha + subject), PR URL, tracker
   issues touched.

## Markdown artifact (on request only)

When the user asks, or as a fallback when `gh` is unavailable: write
`specs/<feature>/pr-<issue-slug>.md` (gitignored — never committed) with one
section per commit: subject, one-line rationale, file list, and the
`git diff <base>...HEAD -- <files>` output for that group.
