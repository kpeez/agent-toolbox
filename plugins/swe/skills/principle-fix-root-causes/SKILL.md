---
name: principle-fix-root-causes
description: "When you debug a failure or are about to apply a fix, trace the symptom to its root cause and fix it there instead of guarding the symptom."
disable-model-invocation: true
---

# Fix root causes

When you debug, do not fix symptoms. Trace every problem to its root cause and
fix it there.

Symptom fixes accumulate. Each workaround makes the system harder to reason
about, and the real bug remains. Root-cause fixes are slower at first but
reduce total debugging time.

## Pattern

- Reproduce first.
- Ask "why" until the answer is a cause you can change, not another symptom.
- Do not add guards. A null check, retry, or catch that silences a crash is a
  symptom fix.
- If a workaround needs a paragraph-long comment to justify it, the code is
  wrong. Fix the code, not the comment.
- Check for the pattern, not just the instance. Search for the same faulty
  pattern, fix each instance in scope, and handle the others per
  [ancillary-fixes](../principle-ancillary-fixes/SKILL.md).
- When you are stuck, instrument. Do not guess. Add logging and read the
  actual error.
- When a probe refutes a hypothesis, revert the changes you made to test it.
- If the deciding fact took a deep dig to find, propose the cheap, always-on
  signal, such as a log line, a metric, or an assertion, that would have shown
  it at first look.

## Restart bugs

When something fails after a restart, suspect stale persisted state before
code, such as config files, caches, lock files, and serialized state. If
clearing a state file restores the behavior, make state validation the fix.

When two fixes that share one premise fail the same check, switch to
[attack-the-premise](../principle-attack-the-premise/SKILL.md).
