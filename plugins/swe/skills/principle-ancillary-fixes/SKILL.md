---
name: principle-ancillary-fixes
description: "When you find an issue outside the task, such as a stale doc, a conflict, a bug, or an unrelated failing check, decide whether to fix it now or report it."
disable-model-invocation: true
---

# Ancillary fixes

An ancillary issue is a problem that the task did not ask about, such as outdated
documentation, a conflict between two sources, a bug, or an unrelated failing
check. What you do depends on your role.

## Lead

You own the task and report to the user.

- Fix the issue when the fix is small, safe, and within the authority of the
  task. The fix counts as task-owned work. Stage and commit it with the task.
- Report the issue instead when the fix is large or risky, needs a decision
  only the user can make, or needs access the task does not give.
- A failing pull-request check follows
  [the CI classification](../ship-pr/references/ci-checks.md#classify-a-failed-check). Only an `in-diff` failure
  earns a fix commit on the branch.
- In the final report, list each ancillary fix and each reported issue apart
  from the main change.

## Bounded worker

You run an assignment for a caller, such as a subagent, a lane, or a campaign worker.

- Report the issue to the caller with its location and evidence. Do not edit
  for it.
- Fix it only when the assignment says so.

The caller then applies the lead rules.
