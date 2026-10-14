# clean-worktrees

Applies when: reclaiming local disk by pruning merged or abandoned git worktrees ("clean up worktrees", "prune safe worktrees", "what's using my disk", "free up space").

You own a safe prune. The audit suggests; the in-use set and the user decide.

This is the one playbook that deletes user state with no code review to catch a slip, so the gates below are the review.

1-snapshot-and-audit: Record `df -h /`, then run `bash <plugin-root>/scripts/worktree_audit.sh [-b origin/<branch>] [repo-path]` ([worktree_audit.sh](../../../scripts/worktree_audit.sh)). Pass `-b` when PRs target a branch other than `origin/HEAD`. It reads paths from `git worktree list`, never hand-typed. Run it in the background, because the session scan is slow. (build-the-lever, encode-lessons-in-structure)
2-cross-check-in-use: The bucket is advice, not permission. The active sessions are the real artifact. Get that set from the user and cross-check every candidate; the in-use set wins over a `safe` bucket. (prove-it-works)
3-verify-usage: For every `verify-recent-chat` row, or any row you doubt, have subagents read this project's session transcripts and report whether the session is ongoing and which worktrees it touches. A background subagent's worktree is in use even when the user never named it. (recall, guard-the-context-window)
4-pause-on-loss: `wip:N` is N tracked uncommitted edits. Show the diff and get a decision first, since uncommitted work is gone once removed. `scratch:N` is untracked throwaway; name the files. Clean, merged, and not in use proceeds. `wip` and in-use pause.
5-prune-confirmed-set: For each confirmed path, run `git worktree remove --force <path>`. When the folder survives on ignored build artifacts, remove it, then run `git worktree prune`. Branch refs survive, so no commits are lost. Confirm with `df -h /` and list the worktrees again.
6-other-reclaimers: When more space is needed, offer package caches (pnpm, uv, brew, yarn). Clear only caches the user has not said to keep.

Reply: `df -h /` before and after with the space reclaimed, the worktrees pruned, and a one-line reason for each one held back (in use by which session, or uncommitted work). No PR.
