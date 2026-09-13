---
name: merge-conflicts
description: Resolve conflicts in an active Git merge, rebase, or cherry-pick while preserving intended behavior.
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
   trade-off. Do **not** invent new behavior. Prefer resolving; abort only when
   the calling workflow explicitly authorizes it.
4. **Verify.** Run applicable project checks and fix anything the merge broke.
   Distinguish failures introduced by the resolution from pre-existing or
   unavailable checks.
5. **Finish when authorized.** Stage only reviewed conflict-resolution paths,
   preserving unrelated staged and unstaged work. Commit a merge or continue a
   rebase/cherry-pick only when the requested operation authorizes that finish;
   otherwise leave the reviewed resolution ready for the caller.
   Before committing or continuing, inspect the entire index: these operations
   can include unrelated staged changes. If finishing would include them, stop
   and ask for direction without unstaging, stashing, or resetting user work.
