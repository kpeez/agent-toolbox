---
name: pr
description: Group current branch diff into atomic commits, push, open a draft PR if missing, and write an markdown artifact rationale into the associated spec. Use when ready to publish branch work.
---

# /pr - Group, Commit, Push, Draft PR

Bundle the committed + uncommitted changes on the current branch (or worktree) into small atomic commits, push, and ensure a draft PR exists. Write an markdown artifact into the spec directory that explains the logical groupings.

## Rules

- **Atomic PRs, atomic commits.** Imperative, conventional-style commit subjects (`feat: ...`, `fix: ...`, `refactor: ...`, `docs: ...`, `test: ...`, `chore: ...`).
- **PR title and body come from PLAN.md, SPEC.md, STATUS.md, linked issues, and the diff.** Do not create `commits.md` or `draft-pr.md` artifacts in the repo.
- **The markdown diff artifact lives only in `specs/<feature>/`**, which is gitignored. It is a private review aid, not a PR comment or repo artifact.
- **Never add agent attribution** (`Co-authored-by`, `Generated with`, etc.).
- **Draft PRs by default.** Mark ready for review only when the user asks.
- **Squash merge by default.** Do not switch merge methods without being asked.

## Command

### /pr [feature-name]

<steps>

<step action="resolve-feature">if argument provided, use it as `<feature>`; otherwise, if `specs/` exists, pick the feature whose `specs/<feature>/STATUS.md` was modified most recently; fall back to legacy `implementation.md` only when no `STATUS.md` exists; if no spec exists, continue without one and skip the markdown artifact step</step>

<step action="read-context">when `<feature>` resolved, read `specs/<feature>/AGENTS.md`, `PLAN.md`, `SPEC.md`, and `STATUS.md` for intent, scope, linked issues, and the desired PR slice</step>

<step action="resolve-base">determine the review base with `git merge-base main HEAD`; fall back to `master` only if `main` does not exist. Record `<base>` and `<branch>` (from `git rev-parse --abbrev-ref HEAD`)</step>

<step action="gather-scope">collect the full branch state: - committed diff: !`git diff --name-status <base>...HEAD` - uncommitted tracked: !`git status --porcelain` - untracked: !`git ls-files --others --exclude-standard`
Inspect file diffs with !`git diff <base> -- <file>` and !`git diff -- <file>` for working-tree changes</step>

<step action="group">cluster every changed file (and within-file hunks if needed) into logical groups. Each group is one coherent intent — one feature slice, one refactor, one fix, one docs/test pass. Avoid mixed-intent commits. Order groups so each commit leaves the tree buildable</step>

<step action="propose">print the proposed grouping: for each group, list the files/hunks, the commit subject, and a one-line rationale. Stop here only if the user previously asked to confirm; otherwise proceed</step>

<step action="commit">for each group in order: - stage exactly that group (`git add <paths>`, or `git add -p` for partial hunks) - commit with the imperative conventional subject and a short body when useful - do not include unstaged leftovers; verify with `git status` between commits</step>

<step action="push">push the branch with upstream tracking when missing: `git push -u origin HEAD`. If upstream is set, plain `git push`. Never force-push without explicit request</step>

<step action="ensure-draft-pr">check for an existing PR with `gh pr view --json number,isDraft,url,title`. If none exists, create a draft: - title and body derived from PLAN.md, SPEC.md, STATUS.md, linked issues, and the diff - `gh pr create --draft --base main --title "<title>" --body "$(cat <<'EOF'\n<body>\nEOF\n)"`
If a PR already exists, leave its state alone (do not flip draft/ready)</step>

<step action="write-markdown">if a spec exists, write `specs/<feature>/pr-<branch>.md` using the Markdown Artifact format below. Overwrite on re-run. Include every logical group, its rationale, and its diff hunks</step>

<step action="update-status">append the PR number and URL to `prs` in `specs/<feature>/STATUS.md` frontmatter and the body if not already present. Then run `python3 skills/spec/scripts/spec-status.py --write` (or `spec/scripts/spec-status.py --write` from an installed skill copy)</step>

<step action="summarize">print the Summary in the format below</step>

</steps>

## Markdown Artifact

Path: `specs/<feature>/pr-<branch>.md` (gitignored — never committed).

One section per logical group with the rationale and a diff fenced code block. Use this skeleton (adapt content; keep it minimal):

````markdown
# PR: <pr-title>

<branch> · base <base> · <pr-url-or-"no PR yet">

## 1. <commit-subject>

<one-line rationale: what intent this group serves and why these files are together>

Files: <file paths, comma-separated>

```diff
<diff output from git diff <base>...HEAD -- <files-in-group>>
```
````

## 2. <commit-subject>

<!-- repeat for each group -->

```

Diff source for each group: `git diff <base>...HEAD -- <files-in-group>` after the commits land (so the artifact reflects what was actually committed).

## Summary Format

```

## PR Summary

- **Branch**: <branch>
- **Base**: <base>
- **Commits created**: <n>
  - <sha-short> <subject>
  - ...
- **Pushed**: yes
- **PR**: <url> (draft) // or "existing PR left as-is: <url>"
- **Markdown artifact**: specs/<feature>/pr-<branch>.md // or "skipped (no spec)"
- **STATUS.md**: updated, specs/STATUS.md regenerated

```

```
