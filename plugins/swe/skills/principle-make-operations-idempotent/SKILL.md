---
name: principle-make-operations-idempotent
description: "When you design a command, a lifecycle step, a job, a retry, or a processing loop that runs amid crashes, restarts, and retries, make every rerun reach the same end state."
disable-model-invocation: true
---

# Make operations idempotent

Design every state-changing operation to converge to the correct state however
many times it runs and wherever the previous run stopped.

Derive each step from the state that exists, not from what the previous run
meant to do. Read the current state, compare it to the goal, and apply only
the difference.

Anything a run leaves behind (a lock, a temporary file, a half-written record,
a claimed job) must be recognizable as stale by the next run. Use evidence
that holds wherever the previous run could have stopped. Write to a temporary
path and rename it into place.

Test:

- What happens if this runs twice?
- What happens if the previous run crashed at each possible point?

If the answer depends on what was left behind, add a reconcile step.
