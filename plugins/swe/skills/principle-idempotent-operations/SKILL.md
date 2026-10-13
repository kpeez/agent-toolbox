---
name: principle-idempotent-operations
description: "When a change adds a migration, job, retry, or resume path: make a rerun, or a resume after a crash at any point, reach the same end state."
user-invocable: false
---

# Idempotent operations

An operation that changes state must reach the same correct end state however
often it runs and wherever an earlier run stopped. Answer three questions for
each such operation:

1. What happens when it runs twice in a row?
2. What happens when the previous run crashed at each possible point?
3. Does a rerun reach the same end state?

If an answer is "it depends on what the last run left", add a reconcile step:

- At start, scan the existing state, clean stale artifacts, and adopt live work
  instead of starting a duplicate.
- Compare by content, not by creation order or timestamps.
- Detect a stale lock, for example by checking that its holder process still
  runs.
- Write to a temporary location and rename into place, so that a crash leaves
  the old state or the new state, not a mix.
- Make a failed unit of work run again cleanly from fresh input.
