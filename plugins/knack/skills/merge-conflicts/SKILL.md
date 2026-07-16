---
name: merge-conflicts
description: Resolve an in-progress git merge, rebase, or cherry-pick conflict by tracing each side's intent, preserving both where possible, and verifying with the project's checks. Use when git reports conflicts or the user asks to resolve a merge/rebase.
user-invocable: false
---

# Merge Conflicts

Textual resolution is the easy part; the failure mode is a **semantic conflict**
— both hunks resolve cleanly but the merged behavior is wrong. The discipline:
trace intent before touching a hunk, and verify behavior after.

1. **See the state.** `git status`, the in-progress operation (merge / rebase /
   cherry-pick), and every conflicting file.
2. **Trace each side's intent.** For each conflict, find *why* each side made
   its change — commit messages, linked PRs, issues. Never resolve a hunk whose
   intent you can't state in one sentence for both sides.
3. **Resolve.** Preserve both intents where possible. Where they're genuinely
   incompatible, pick the side matching the merge's stated goal and note the
   trade-off. Do **not** invent new behavior. Always resolve; never `--abort`.
4. **Verify.** Run the project's checks — typecheck, tests, lint/format — and
   fix anything the merge broke. This is what catches semantic conflicts.
5. **Finish.** Stage everything and commit; if rebasing, `--continue` until all
   commits are replayed.
