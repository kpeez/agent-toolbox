---
name: maintain-formal-verification-skill
description: "Bring a project's formal verification back in line with the code after the code changes: find the commits that touched verified code, update the model, harness, or properties to describe the code as it is now, rerun, and say whether each failure is drift in the verification or a bug in the code. Use for /maintain-formal-verification-skill, \"is the model still true to the code\", or after merges and refactors that touched verified code without rechecking it."
argument-hint: "[verify skill or area]"
disable-model-invocation: true
---

# /maintain-formal-verification-skill

A formal check proves a property of what it describes. When the code changes
and the verification does not, the check can keep passing on code that no
longer exists. That pass is the dangerous case, because it looks like a proof.

This skill is the upkeep loop for a verify skill that
[create-formal-verification-skill](../create-formal-verification-skill/SKILL.md)
generated, or for any project-local skill that runs a model checker, prover,
or code-level verifier against named code. The project-local skill handles a
change that an agent makes while it uses that skill. This skill handles the
changes that skipped it: merges, edits made without the skill, and drift
across many commits.

## Outcomes

Give each check one outcome, and say which:

- **in sync**: no change since the last sync alters what the check describes,
  and the check passes.
- **updated**: the code changed, the verification now describes the new code,
  and the check passes.
- **bug**: the verification describes the current code, and the code breaks
  the property. This is a finding about the code, not drift.
- **blocked**: the check could not be brought back in line or could not run.
  Say exactly why.

A check can be both updated and bug: the update makes the verification
describe the code again, and then the property fails on it.

## Edit scope

Edit only the verification: models, harnesses, property files, and the verify
skill itself. Do not edit product code unless the user asks. When a property
fails on the current code, do not weaken the property or the model to make it
pass. Report the failure.

## Steps

1. `1-find-the-checks`: Find each verify skill by what it does: a project
   skill that runs a model checker, a prover, or another verifier against
   named code. Read each one, or the one the user named. For each check,
   collect the property, the code it covers, the bounds and assumptions, the
   command, and the sync commit: the commit where it was last confirmed to
   describe the code. When no verify skill exists, stop and point to
   `create-formal-verification-skill`. When the skill records no sync commit,
   use the last commit that changed the verification files, and say so.
2. `2-run-as-is`: Run each check once before you change anything, and record
   the result. A pass here says only that the old description still holds. A
   failure here can be drift or a bug. Do not decide which before step 5.
3. `3-read-covered-changes`: Diff the covered files from the sync commit to
   the current commit, and read each commit message. Code that moved is still
   covered code: a covered function that is renamed, split, or moved to
   another file. New code that touches the state a check guards, such as a new
   function that writes the same fields, is covered code too. Put each change
   in one class:
   - **No effect.** The change alters nothing that the verification
     describes, such as formatting, comments, or uncovered paths. Check this
     against the model or harness, not against the commit message.
   - **Stale description.** A step that was one indivisible action is now
     two, a branch was added or removed, a check moved, a new path reaches the
     guarded state, or a value now has a different range. The model or harness
     must change.
   - **Promise changed on purpose.** The change alters what the code
     promises, and evidence in the change says so: the doc comment, the tests,
     the changelog, or the commit message. The property must change. Cite the
     evidence.
   - **Promise may be broken.** The code changed, and no evidence says that
     the promise changed. Treat a failure that follows as a bug candidate.
4. `4-update-from-code`: Change the model or harness so that each changed part
   again points to code that a reviewer can open. Keep one indivisible step in
   the code as one step in the verification. Write the update from the code
   before you rerun. Do not shape it by what makes the check pass. Change a
   property only for a promise that changed on purpose, and record the old
   wording, the new wording, and the evidence. Keep the bounds unless the
   change makes them wrong. Report any bound you reduce.
5. `5-rerun-and-judge`: Rerun each check.
   - **Pass:** the new description can have lost the ability to fail. Break
     the new code the way the property guards against, such as a removed
     check or a reordered step, and confirm that the check catches it. Then
     drop the break.
   - **Fail:** replay the counterexample against the real code, step by step.
     When a step cannot happen in the code, the verification is wrong. Fix it,
     and say what was wrong. When every step can happen, it is a bug. Name the
     commit that introduced it, give the counterexample as steps in the code's
     words, and state the harm in one sentence. When a cheap test or
     reproduction against the real code shows the bug, add it to the report as
     evidence. Do not commit it to product code.
6. `6-update-the-verify-skill`: Update the covered code, the commands, the
   bounds, the assumptions, and the sync commit of each check. Set the sync
   commit to the commit you checked. Do not move it for a blocked check, and
   say so. Then follow the verify skill once as the next agent would, to show
   that its steps still run.

## Report

For each check, give:

- the outcome, and the commits you read;
- what changed in the verification and why: the code changed shape, or the
  promise changed on purpose, with the evidence;
- the rerun result, and the break that shows the updated check can still fail;
- each bug in plain words: the counterexample as steps in the code's words,
  the harm, and the commit that introduced it;
- what the verification still does not cover, including new code that it
  should cover.

Say which failures were drift in the verification and which were bugs in the
code. For a check that passed before the update and fails after, say that the
old pass was on a stale description.

Put the verification updates in a change of their own, separate from any
product fix.
