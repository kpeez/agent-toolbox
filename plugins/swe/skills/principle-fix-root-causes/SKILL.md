---
name: principle-fix-root-causes
description: "When you debug a failure or are about to apply a fix, trace the symptom back to the first place the system went wrong and fix it there. A guard is a fix only when the state it handles is legitimate."
disable-model-invocation: true
---

# Fix root causes

When you debug, fix the fault, not the place where it surfaced. The symptom
is where a wrong state became visible. The root cause is the first place the
system did something it must not do, or failed to handle a state it must
handle.

A symptom fix hides the evidence and leaves the fault free to surface
somewhere else. Each one makes the system harder to reason about, because the
code now carries a workaround for a bug that nobody named.

## Pattern

- Reproduce first.
- Ask "why" at each step until the answer is a wrong decision in the code,
  not a consequence of an earlier one.
- When you are stuck, instrument. Read the actual error and the actual state.
  Do not guess.
- Ask whether the state that triggered the symptom is legitimate. If the
  system may be in that state, the code that broke on it is the root cause,
  and handling the state there is the fix. If the state must never exist, a
  check where it broke hides the bug. Find what produced the state. Guards,
  retries, swallowed errors, clamped values, and discarded state are the
  usual ways to hide a bug.
- When something fails only after a restart, suspect persisted state first,
  such as config files, caches, lock files, and serialized state.
- Check for the pattern, not just the instance. Find every place with the
  same fault, fix each instance in scope, and handle the others per
  [ancillary-fixes](../principle-ancillary-fixes/SKILL.md).
- When a probe refutes a hypothesis, revert the changes you made to test it.
- If a workaround needs a paragraph-long comment to justify it, the code is
  wrong. Fix the code, not the comment.
- If the deciding fact took a deep dig to find, propose the cheap, always-on
  signal, such as a log line, a metric, or an assertion, that would have shown
  it at first look.

When two fixes that share one premise fail the same check, switch to
[attack-the-premise](../principle-attack-the-premise/SKILL.md).
