---
name: principle-separate-shared-state
description: "When two workers, processes, or agents would write the same file, branch, key, or state object: give each its own state before you add a lock."
disable-model-invocation: true
---

# Separate shared state

Concurrent writes to one target cause races that are intermittent and hard to
reproduce.

1. Find the shared mutable state: a file that two actors write, a branch that
   both push to, or a key that both update.
2. By default, remove the shared write target. Ask whether the actors need one
   canonical object or only publish independent facts. Give each actor its own
   file, key, branch, worktree, or state directory, and merge at the read or
   report step. Two workers that each write their own field into one
   `state.json` still share it; `indexer-state.json` and `metrics-state.json`
   do not.
3. Only when one shared target is a real invariant, serialize access in the
   structure: a single-writer owner, sequential phases, a lock file, or an
   atomic compare-and-swap. An instruction to take turns is not concurrency
   control.
