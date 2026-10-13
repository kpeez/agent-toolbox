---
name: principle-fix-root-causes
description: "Before you apply a bug fix, and after a fix fails: find the root cause and fix it there, sweep for the same pattern, and do not guard the symptom."
user-invocable: false
---

# Fix root causes

Fix a failure where it starts, not where it shows.

- Reproduce first. When you are stuck, instrument the code and read the actual
  error.
- Ask why until the answer is a cause you can change, not another symptom.
- Do not add a guard, null check, retry, or catch that only silences the
  symptom. A workaround that needs a long comment to justify it marks the wrong
  fix.
- When a failure starts after a restart, suspect stale persisted state first:
  config files, caches, lock files, and serialized state.
- After you find the cause, search for the same faulty pattern elsewhere. Fix
  each instance in scope, and handle the others per
  [ancillary-fixes](../principle-ancillary-fixes/SKILL.md).
- When a probe refutes a hypothesis, revert the changes you made to test it.

## After two failed fixes

When two fixes that rest on one premise fail the same check, stop fixing.

1. Write the premise as one sentence: the fact that every failed fix assumed.
2. Test the premise directly before the next fix. For example, count where the
   failure occurs per actor, input, or run.
3. If the counts are even, the premise is not the cause. Look elsewhere and
   keep the counts as evidence.
4. If a few actors hold most of the failure on every run, find what gives them
   that role. Remove the asymmetry; do not compensate for it.
