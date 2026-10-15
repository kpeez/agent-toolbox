---
name: no-comments
description: "Spawn Comment Sicko to delete comments, fix the accepted findings, and offer encodings for claimed constraints."
argument-hint: "[path or diff]"
disable-model-invocation: true
---

# No comments

Spawn Comment Sicko. Act on the findings you accept. Defer to its fresh
perspective.

## Scope

Use the caller's files or diff. Otherwise use the current diff against the
base branch, default `main`, including the working tree.

## Steps

1. Spawn Comment Sicko and pass it the scope. In Claude Code, use the Agent
   tool with `swe:comment-sicko`. In Codex, spawn the `comment-sicko`
   subagent. Do not restate its rules.
2. Inspect its report and diff. Reject application-code edits, scope escapes,
   deletions that an exception protects, misstated `MUST KILL` reasons, and
   flags that treat kept intentional code as guilty. Reshape flags on
   surprises in our own code stay actionable. Do not restore those comments.
   A keep survives only with proof that it is about something we cannot
   change. Audit scoped lint and TypeScript suppressions it missed.
   Correctness or safety suppressions stay actionable `MUST KILL` flags.
   Restore a deletion only with an exact exception and scoped proof. Before
   you accept a thin `IMPORTANT` or `do not remove` kill or keep, run the
   `how` or `why` skill on its symbol. If a kill is ambiguous, do not restore
   it. If a keep is refuted or still ambiguous, delete it. Revert one rejected
   report and rerun Comment Sicko with the failure named. Reject a second bad
   report, report it open, and fail `no-comments`.
3. Fix trivial accepted flags directly: delete a dead path, drop a parameter,
   or use the real API. If any fix needs a new shape, run the `architect`
   skill once for the accepted set and the code around it. Stop at the
   sketch. Architect shapes the fix. Step 4 implements it.
4. Implement the smallest root-cause fix in scope. Remove every named
   workaround. If the root cause is out of scope, land the smallest in-scope
   fix and report the rest open. The `principle-fix-root-causes` and
   `principle-redesign-from-first-principles` skills guide intent only.
   Neither one lets you widen the scope or fix instances outside it. Never
   add symptom guards.
5. Constraint comments say `do not remove`, `do not change wording`, or `talk
   to X before changing`. Leave keeps about things we cannot change. For the
   others, offer the cheapest in-scope type, runtime check, test, or CI lint
   that enforces the constraint. Wait for the user's approval. An unattended
   run or an eval needs the caller's approval in advance. If approved, encode
   the constraint, then delete the comment. Otherwise delete the comment,
   report the constraint open, and sketch the out-of-scope work.
6. Report the deletion count, restored comments, reruns, the architect
   sketch, fixes, encoding offers, encodings, unenforced constraints, and
   other open work.
