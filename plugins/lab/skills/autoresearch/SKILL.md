---
name: autoresearch
description: Run a bounded autonomous experiment loop against an approved metric and evaluator. Use for autoresearch or repeated optimization runs.
---

# Autoresearch

Run one linear experiment loop: make a small change, commit it, evaluate that
exact commit, then keep or discard it according to the approved program. Rules
that vary by run live in `program.md`; this skill defines the stable loop. The
historical [Karpathy prompt](references/karpathy-program.md) is provenance only;
its TSV, branch, fixed-budget, and infinite-loop rules are not active.

For a new run, read [setup and program approval](references/setup-program.md).
When resuming, read [interrupted-run reconciliation](references/resume-reconciliation.md).
Read only the phase reference needed for the current state. An approved program
must define the iteration unit before candidate optimization. If existing
evidence or a simple bounded pilot cannot establish it, the setup reference
requires a bounded calibration as the first experiment, followed by a
comparable baseline at the selected unit.

## Experiment boundaries

Everything inside the editable paths is available for experiments. Do not:

- modify the evaluator or another read-only path;
- add dependencies unless the program allows it;
- write evaluator output outside declared output paths;
- exceed a soft constraint dramatically, even for a better metric.

All else equal, simpler wins only under the approved tie policy. Prefer deleting
over simplifying, simplifying over optimizing, and optimizing over automating.
Do not keep an equal metric for subjective simplicity unless the program
authorized that judgment.

## Evaluate and record attempts

Every candidate evaluator invocation is one attempt with one committed code
state, one log, and one record in the candidate ledger, including crashes and
retries. Calibration, when needed, has its own record and log directories so that the
candidate ledger starts with the comparable baseline; see the setup reference.

1. Determine the next ledger ID before invoking the evaluator. Use one loop
   writer; do not reserve IDs concurrently.
2. Record the full `HEAD` commit and write output to
   `<log-dir>/<id>-<full-sha>.log`. Never reuse or overwrite a log.
3. Run the evaluator exactly as approved, redirecting stdout and stderr to that
   log. Do not stream evaluator output into context.
4. Check the evaluator's exit status and extract metrics with the approved
   command. A nonzero exit, unusable metrics, or a killed process is a crash.
   Inspect only the bounded tail needed to diagnose it.
5. Append exactly one ledger record for this invocation. The record's commit
   must be the commit named by the log and actually evaluated.

If a crash has a trivial code fix, record the failed attempt first. Make the
fix, commit it, then evaluate the new commit under a new ID and log. Never
reuse the previous commit, ID, or log for a retry. If the idea itself is broken,
record the crash and discard it.

Use the recorded ledger script:

```bash
python3 <ledger.py> append <record-dir> \
  --commit <full-sha> --status keep --description "baseline" \
  --metric val_bpb=0.9979 --metric peak_vram_gb=44.0
```

`status` is `keep`, `discard`, or `crash`. Use `key=null` when a crash produced
no measurement. The ledger is append-only. Never rewrite, reorder, or delete
its lines. If a record is wrong, stop and report the discrepancy; a later line
does not silently change the earlier record. `ledger.py render <record-dir>`
rebuilds the summary from the ledger.

## The loop

Initialize the run once before entering the repeated candidate loop:

1. If the approved program requires calibration, complete it in the separate
   calibration ledger, select a practical unit by its declared criteria, and
   record that decision. Hold the selected unit fixed. Do not tune the
   evaluator to favor a candidate. Recalibration requires comparable evidence
   and must not mix incompatible measurements.
2. Establish and record the comparable unmodified baseline at the selected
   unit in the candidate ledger. The baseline is its first `keep`. Do not repeat
   calibration or baseline setup on later iterations.

Then repeat the candidate loop until the approved stop condition:

1. Start from the latest kept candidate commit with a clean worktree. Before
   editing or resetting, inspect `git status --short --untracked-files=all`.
   Declared, ignored evaluator outputs may remain; anything else stops the loop.
2. Pick one idea and make the smallest change that tests it.
3. Commit the code that will be evaluated. The commit is the experiment's
   identity.
4. Evaluate and record the attempt as described above.
5. Keep an improved metric. Keep an equal metric only when the approved tie
   policy allows the demonstrated simplification. Otherwise discard it.
6. After a discard or a crash that will not be retried, verify the expected
   worktree and branch, confirm the status contains no unexpected paths, and
   verify the target kept commit with `git cat-file -e <sha>^{commit}`. Only
   then reset the experiment branch to that commit. Never start the next idea
   from an abandoned crashed candidate. The attempt remains identified in the
   ledger.
7. Check the stop condition. If it is unmet, continue.

When an evaluation exceeds the kill threshold, terminate it and record a crash.
Do not pause mid-loop merely to ask whether to continue. Stop for the approved
condition, user interruption, unsafe or unreconciled state, or a missing
required capability. When ideas run thin, revisit in-scope code and retained
results within the remaining budget; do not broaden scope.

## Wrap-up

When the run stops, render the candidate and calibration summaries and report
the latest kept candidate commit and metrics versus the comparable baseline,
the selected unit and calibration result and budget, candidate attempts and
keeps, stop reason, branch, worktree, both record directories when used, and
any unreconciled state. Leave the branch and worktree in place. Merging,
publishing, or discarding the result remains the user's choice.
