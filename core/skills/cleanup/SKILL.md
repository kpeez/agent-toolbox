---
name: cleanup
description: Aggressively simplify and clean up new code after implementation. Use after finishing a feature and before /spec-review to reduce verbosity, remove unnecessary complexity, and tighten the diff.
---

# /cleanup - Post-Implementation Code Cleanup

## Command

- **Review the current branch state, not just HEAD.** Scope is `merge-base(main, HEAD)` to the current working tree, plus untracked files.
- **Never create temporary commits, stashes, or branches to manufacture a diff.**
- **If the working tree is clean, use the same flow anyway; it will naturally reduce to committed branch changes only.**

### /cleanup [feature-name]

Review new/changed code on the branch and aggressively simplify it.

<steps>
<step action="resolve-feature">if argument provided, use it as `<feature>`; otherwise, if `specs/` exists, pick the feature whose `specs/<feature>/STATUS.md` was modified most recently; fall back to legacy `implementation.md` only when no `STATUS.md` exists</step>
<step action="read-context">when `<feature>` resolved, read `specs/<feature>/AGENTS.md`, `specs/<feature>/PLAN.md`, `specs/<feature>/SPEC.md`, and `specs/<feature>/STATUS.md` for intent and scope; for legacy specs, accept `design.md` and `implementation.md` instead</step>
<step action="resolve-base">determine review base with `git merge-base main HEAD`; fallback to `master` only if `main` does not exist</step>
<step action="gather-scope">review the full current branch state against the base commit:
    - tracked files: !`git diff --name-status <base>`
    - untracked files: !`git ls-files --others --exclude-standard`
this is the complete in-scope set</step>
<step action="review">for tracked files, inspect !`git diff <base> -- <file>` so the review includes both committed branch changes and current staged/unstaged edits; for untracked files, inspect the full file contents</step>
<step action="simplify">apply fixes directly — rewrite, inline, delete; do not just suggest changes</step>
<step action="verify">run lint, type checks, and tests after changes to confirm nothing broke</step>
<step action="summarize">print a short summary of what was simplified and why</step>
</steps>

## Cleanup Checklist

Work through each category against the diff. Be aggressive — the default is to simplify, not to preserve.

### 1. Verbosity and Line Count

- Could any block be rewritten in significantly fewer lines without losing clarity?
- Are there multi-line constructs that should be single expressions (comprehensions, ternaries, chained calls)?
- Are there unnecessary intermediate variables that obscure rather than clarify?
- Is there boilerplate that a stdlib function or existing helper already handles?

### 2. Over-Abstraction

- Are there classes/wrappers/base classes for things used exactly once?
- Are there abstractions introduced "for flexibility" that nothing currently uses?
- Are there factory functions, builders, or registries for trivially constructable objects?
- Could any class just be a function? Could any function just be inlined at the call site?

### 3. Duplication

- Are there near-duplicate functions that differ by one parameter? Merge them.
- Are there repeated code patterns that should be a helper? Extract them.
- Is there copy-paste code across the diff? Consolidate.

### 4. Dead Code

- Are there imports, variables, functions, or parameters introduced by this diff that are now unused?
- Are there branches or conditions that can never be reached?
- Are there commented-out blocks or TODO placeholders with no associated task?

### 5. Naming and Structure

- Are names precise? (`data`, `result`, `info`, `manager` are red flags)
- Do function signatures match the project's conventions (RORO, keyword args)?
- Is the code in the right file/module, or was it dumped somewhere convenient?

### 6. Error Handling & State Discipline

- Is there defensive code guarding against impossible states? Trust the type system.
- Are there try/except blocks that catch too broadly or swallow errors?
- Are there default/fallback values hiding bugs? (prefer assert over silent default)
- Can any function's argument count be reduced? Are optional params actually always provided?
- Are there loose object types that should be discriminated unions with exhaustive handling?
- Could any nested if/else chain be flattened with early returns?

### 7. Over-Engineering

- Are there configuration options nobody asked for?
- Are there plugin systems, hooks, or event emitters for a single use case?
- Is there premature optimization (caching, pooling, batching) without evidence of need?

## Rules

- **Only touch code from this branch's diff.** Do not "improve" pre-existing code.
- **Bias toward deletion.** Less code is almost always better.
- **Preserve behavior.** Simplify implementation, not semantics. Tests must still pass.
- **Don't be precious.** If you wrote it 20 minutes ago and it's overcomplicated, rewrite it.
- **Apply the 50-line test.** If 200 lines could be 50, rewrite it. If 50 could be 20, rewrite it.
- **One pass, then stop.** Don't loop endlessly. One focused cleanup pass is enough.

## Summary Format

After cleanup, print:

```
## Cleanup Summary
- **Files touched**: <count>
- **Lines before**: <approx>
- **Lines after**: <approx>
- **Key changes**:
  - <what was simplified and why, one bullet per file or logical change>
```
