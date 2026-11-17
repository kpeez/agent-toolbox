---
name: principle-separate-before-serializing-shared-state
description: "When concurrent workers, processes, or agents might write the same file, branch, key, or state object, remove the sharing first and serialize only when one shared writer is a real invariant."
disable-model-invocation: true
---

# Separate before serializing shared state

When concurrent actors might write the same file, branch, key, or object,
first ask whether they need one shared object or only publish independent
facts. By default, give each actor its own file, key, branch, or state
directory, and merge only where the state is read. Two workers that each write
their own field into one `state.json` still share mutable state.

Serialize only when one shared write target is a real invariant. Do it in the
structure, with a lock file, a single writer, sequential phases, or
compare-and-swap. Instructions are not concurrency control. Treat "we need a
lock" as a smell to check first.
