---
name: spec-review
description: Review branch changes and draft commit and PR plans. Use when the user asks to split work into logical commits, write conventional commit messages, or generate `commits.md` and `draft-pr.md` for a spec.
---

# /spec-review - Commit and PR Drafting

## Command

### /spec-review [feature-name]

Review branch changes and generate commit + PR planning docs.

<steps>
<step action="resolve-feature">if argument provided, use it as `<feature>`; otherwise, if `specs/` exists, pick the feature whose `specs/<feature>/implementation.md` was modified most recently</step>
<step action="resolve-output">if `<feature>` is resolved, write outputs to `specs/<feature>/`; otherwise write to repo root</step>
<step action="validate-context">when writing to `specs/<feature>/`, error if that directory does not exist; read `AGENTS.md` plus `specs/<feature>/AGENTS.md` and `specs/<feature>/implementation.md` first</step>
<step action="resolve-base">determine review base using merge-base with upstream (`@{upstream}`); fallback to merge-base with `main`, then `master`</step>
<step action="review-diff">review all branch changes with `git diff --name-status <base>...HEAD` and `git diff <base>...HEAD`; separate in-scope and unrelated files</step>
<step action="write-commits">write `commits.md` using the template below; group changes into concrete logical commits with conventional commit subjects</step>
<step action="write-draft-pr">write `draft-pr.md` using `commits.md` as the source of truth for title, scope, grouped changes, and testing plan</step>
</steps>

<template file="<output-dir>/commits.md">
# <Feature or Branch> - Commit Plan

## Scope Reviewed
- Branch: <branch-name>
- Base: <base-ref>
- Spec: `specs/<feature>/` or `n/a`
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
