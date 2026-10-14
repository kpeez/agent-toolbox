---
name: principle-make-operations-idempotent
description: "When you design a command, a lifecycle step, a job, a retry, or a processing loop that runs amid crashes, restarts, and retries, make every rerun reach the same end state."
disable-model-invocation: true
---

# Make operations idempotent

Design operations so that they converge to the correct state however many
times they run and wherever an earlier run stopped. Every state-changing
operation must answer two questions. What happens if this runs twice? What
happens if the previous run crashed halfway?

Commands, lifecycle operations, and processing loops run where crashes,
restarts, and retries are normal. If partial state changes the outcome of the
next run, every restart becomes a debugging session.

## Pattern

- **Convergent startup.** Scan for existing state, clean stale artifacts, and
  adopt live sessions instead of starting a duplicate.
- **Content-based cleanup.** Compare by content, not by creation order or
  timestamps.
- **Self-healing locks.** Detect a stale lock, for example by checking that
  the process ID that holds it still runs.
- **Atomic writes.** Write to a temporary location and rename into place, so
  that a crash leaves the old state or the new state, not a mix.
- **Idempotent scheduling.** Failed work runs again cleanly, and fresh input
  is regenerated after each cycle.

## Test

1. What happens if this runs twice in a row?
2. What happens if the previous run crashed at each possible point?
3. Does a rerun converge to the same end state?

If any answer is "it depends on what state was left behind", the operation
needs a reconcile step.
