---
name: principle-separate-before-serializing-shared-state
description: "When concurrent workers, processes, or agents might write the same file, branch, key, or state object, remove the sharing first and serialize only when one shared writer is a real invariant."
disable-model-invocation: true
---

# Separate before serializing shared state

When concurrent actors might share mutable state, first ask whether they need
the same mutable object. If not, remove the sharing. When the sharing is real,
enforce serialization in the structure, with lock files, sequential phases, or
exclusive ownership. Instructions and conventions are not concurrency control.

Concurrent writes to shared state cause races that are intermittent, hard to
reproduce, and expensive to debug.

1. **Find the shared mutable state**, such as a file that two actors read and
   write, a branch that both push to, or an API that one defines while the
   other consumes it.
2. **By default, remove the shared write target.** Ask whether the actors need
   one canonical object or only publish independent facts. Give each actor
   its own file, key, branch, worktree, or state directory, and merge only at
   the read or report step. Two workers that each write their own `lastX`
   field into one `state.json` still share it. `indexer-state.json` and
   `metrics-state.json` do not.
3. **Only when one shared write target is a real invariant, serialize access
   in the structure**, with a single-writer owner, sequential phases, a lock
   file, or an atomic compare-and-swap. Treat "we need a lock" as a design
   smell to check, not as the default answer.
