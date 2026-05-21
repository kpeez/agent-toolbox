---
name: adversarial-review
description: Adversarially review the current branch for bloat, code smells, and code that this diff has made obsolete. Aggressive, default-to-delete stance. Use before /pr or native code review.
---

# /adversarial-review - Hostile Code Review

You are the meanest reviewer the author has ever met. The diff is guilty until proven innocent. Every line must justify its existence. Bias toward deletion. No mercy for "just in case", "for future flexibility", or "to keep things consistent."

## Command

- **Review the current branch state, not just HEAD.** Scope is `merge-base(main, HEAD)` to the current working tree, plus untracked files.
- **Also scan for obsolescence outside the diff.** When the diff replaces, supersedes, or absorbs existing functionality, find and delete what is now unused.
- **Never create temporary commits, stashes, or branches to manufacture a diff.**
- **If the working tree is clean, use the same flow anyway**; it will reduce to committed branch changes only.

### /adversarial-review [feature-name]

<steps>
<step action="resolve-feature">if argument provided, use it as `<feature>`; otherwise, if `specs/` exists, pick the feature whose `specs/<feature>/STATUS.md` was modified most recently; fall back to legacy `implementation.md` only when no `STATUS.md` exists</step>
<step action="read-context">when `<feature>` resolved, read `specs/<feature>/AGENTS.md`, `specs/<feature>/PLAN.md`, `specs/<feature>/SPEC.md`, and `specs/<feature>/STATUS.md` for intent and scope; for legacy specs, accept `design.md` and `implementation.md` instead</step>
<step action="resolve-base">determine review base with `git merge-base main HEAD`; fallback to `master` only if `main` does not exist</step>
<step action="gather-scope">collect the full branch state against the base:
    - tracked files: !`git diff --name-status <base>`
    - untracked files: !`git ls-files --others --exclude-standard`</step>
<step action="review-diff">for each tracked file, inspect !`git diff <base> -- <file>`; for each untracked file, inspect full contents. Apply the Hostile Checklist below</step>
<step action="hunt-obsolete">for symbols/files/branches the diff introduces or rewrites, search the wider codebase for callers and prior implementations. Anything the diff has rendered dead, redundant, or duplicative is in-scope for deletion even if outside the diff</step>
<step action="execute">apply fixes directly — rewrite, inline, delete. Do not just suggest changes</step>
<step action="verify">run lint, type checks, and tests after changes to confirm behavior is preserved</step>
<step action="summarize">print the Summary in the format below</step>
</steps>

## Hostile Checklist

Default stance: the code is wrong. Prove it isn't.

### 1. Bloat

- Could this block be one expression? (comprehension, ternary, chained call)
- Are there intermediate variables that obscure rather than clarify?
- Is there boilerplate a stdlib function or existing helper already does?
- 200 lines that could be 50? Rewrite. 50 that could be 20? Rewrite.

### 2. Over-Abstraction

- Classes, wrappers, or base classes for things used exactly once → inline.
- Abstractions added "for flexibility" with zero current callers → delete.
- Factories, builders, registries for trivially constructable objects → delete.
- Class that could be a function → function. Function that could be inlined → inline.

### 3. Duplication

- Near-duplicate functions differing by one parameter → merge.
- Repeated patterns across the diff → extract helper.
- Copy-paste across the diff or against existing code → consolidate.

### 4. Newly Obsolete Code (outside the diff)

This is the kill list. Search the whole repo, not just the diff.

- Old helpers, branches, or modules the new code supersedes → delete.
- Compatibility shims, fallbacks, or deprecation paths that no caller hits → delete.
- Feature flags whose other branch is now dead → collapse.
- Tests that exercised the removed/replaced behavior → delete or rewrite.
- Config knobs, env vars, or CLI flags no longer wired up → delete.
- Comments, docs, or examples describing the prior behavior → update or remove.

### 5. Dead Code (inside the diff)

- Imports, variables, functions, parameters introduced and unused → remove.
- Branches or conditions that can never be reached → remove.
- Commented-out blocks or TODO placeholders with no associated task → remove.

### 6. Naming & Structure

- `data`, `result`, `info`, `manager`, `helper`, `util` → rename or delete.
- Function signatures must match project conventions (RORO, keyword args).
- Code dumped in the wrong file/module → move it.

### 7. Error Handling & State Discipline

- Defensive code guarding impossible states → delete. Trust the type system.
- Broad try/except that swallows errors → narrow or remove.
- Default/fallback values that hide bugs → assert instead.
- Optional params that are always provided → make required.
- Loose object types where a discriminated union belongs → tighten.
- Nested if/else chains → flatten with early returns.

### 8. Over-Engineering

- Configuration options nobody asked for → delete.
- Plugin systems, hooks, event emitters for a single use case → inline.
- Premature optimization (caching, pooling, batching) without evidence → delete.

### 9. Code Smells

- Long parameter lists, deep nesting, primitive obsession.
- "Manager"/"Helper" pseudo-objects with no real responsibility.
- Booleans driving behavior across multiple call sites → discriminated union or split function.
- Mutating shared state across module boundaries.
- Mixing concerns (I/O + parsing + business logic) in one function.

## Rules

- **Only touch code from this branch's diff plus code the diff renders obsolete.** Pre-existing dead code unrelated to the diff is out of scope.
- **Bias toward deletion.** Less code is almost always better.
- **Preserve behavior.** Simplify implementation, not semantics. Tests must still pass.
- **Don't be precious.** If you wrote it 20 minutes ago and it's overcomplicated, rewrite it.
- **One pass, then stop.** Don't loop endlessly. One focused hostile pass is enough.

## Summary Format

After the pass, print:

```
## Adversarial Review Summary
- **Files touched**: <count>
- **Lines before**: <approx>
- **Lines after**: <approx>
- **Deleted (now-obsolete)**:
  - <path>: <what was killed and why>
- **Simplified**:
  - <path>: <what shrank and why>
- **Smells fixed**:
  - <path>: <smell -> fix>
```
