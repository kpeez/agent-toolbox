---
name: ship
description: Prepare finished branch work for shipping by reviewing scope, grouping logical commits, and drafting PR material. Use when the user asks to split work into commits, write conventional commit messages, create a PR draft, or close out a spec for review/merge.
---

# /ship - Branch Closeout

## Command

### /ship [feature-name]

Prepare branch changes for shipping by generating commit + PR planning docs.
This is not a substitute for a native agent `/review` or hosted PR review. Use
those for bug-finding and regressions; use `/ship` for packaging, commit
boundaries, PR narrative, and verification summary.

Never add agent attribution to generated commit or PR material. Do not include
`Co-authored-by`, `Signed-off-by`, `Generated with`, AI tool signatures, agent
names, or agent entries in contributors lists.

<steps>
<step action="resolve-feature">if argument provided, use it as `<feature>`; otherwise, if `specs/` exists, pick the feature whose `specs/<feature>/STATUS.md` was modified most recently; fall back to legacy `implementation.md` only when no `STATUS.md` exists</step>
<step action="resolve-output">if `<feature>` is resolved, write outputs to `specs/<feature>/`; otherwise write to repo root</step>
<step action="validate-context">when writing to `specs/<feature>/`, error if that directory does not exist; read `AGENTS.md` plus `specs/<feature>/AGENTS.md`, `specs/<feature>/PLAN.md`, `specs/<feature>/SPEC.md`, and `specs/<feature>/STATUS.md` first; for legacy specs, accept `design.md` and `implementation.md` instead</step>
<step action="resolve-base">determine review base with `git merge-base main HEAD`; fallback to `master` only if `main` does not exist</step>
<step action="review-diff">review the entire current branch state against the base commit:
- tracked files from `git diff --name-status <base>`
- untracked files from `git ls-files --others --exclude-standard`
- inspect tracked file diffs with `git diff <base> -- <file>`
- inspect full contents of untracked files
- write `commits.md` and `draft-pr.md` from that total scope
- never require or create a temporary commit</step>
<step action="write-commits">write `commits.md` using the template below; group changes into concrete logical commits with conventional commit subjects</step>
<step action="write-draft-pr">write `draft-pr.md` using `commits.md` as the source of truth for title, scope, grouped changes, and testing plan</step>
</steps>

<template file="<output-dir>/commits.md">
# <Feature or Branch> - Commit Plan

## Scope Reviewed

- Branch: <branch-name>
- Base: `<merge-base-with-main>`
- Spec: `specs/<feature>/` or `n/a`
- Review target: `current branch worktree`
- In-scope files:
  - `<path>`
- Out-of-scope files (if any):
  - `<path>`

## Logical Commits

### 1. `<type>(<scope>): <subject>`

- Why: <reason this commit boundary is useful>
- Files:
  - `<path>`
- Changes:
  - <specific behavior/code/docs change>
- Verification:
  - <test/check/example>
    </template>

<template file="<output-dir>/draft-pr.md">
# `<type>(<scope>): <overall PR title>`

<one-sentence description> This PR {does what? why?}<one-sentence description>

## Summary

- <high-level outcome>
- <high-level outcome>

## Why

- <problem or context>

## Changes

- <bullet list of grouped changes aligned with `commits.md`. this should capture the changes in LOGIC as well as the changes in IMPLEMENTATION>

## Testing

- [ ] <command/check>
- [ ] <command/check>

</template>
