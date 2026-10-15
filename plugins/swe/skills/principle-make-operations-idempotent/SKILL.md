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

## Idea

Derive each step from the state that exists, not from what the previous run
meant to do. Read the current state, compare it to the goal, and apply only
the difference. A step written this way is safe to repeat, because a repeat
finds nothing left to do.

Anything a run leaves behind, such as a lock, a temporary file, a
half-written record, or a claimed job, must be recognizable as stale by the
next run. Judge staleness by evidence that stays true wherever the previous
run could have stopped, not only in the common case. A marker that the next
run cannot judge turns every crash into manual cleanup. For example, write to
a temporary path and rename it into place, or compare artifacts by content
instead of by creation order.

## Test

1. What happens if this runs twice in a row?
2. What happens if the previous run crashed at each possible point?
3. Does a rerun converge to the same end state?

If any answer is "it depends on what state was left behind", the operation
needs a reconcile step.
