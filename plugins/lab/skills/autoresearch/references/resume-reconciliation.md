# Autoresearch interrupted-run reconciliation

Use this reference only when resuming an approved run. Resume from observed
state, not from an assumed ledger position. The root skill owns the loop and
stop condition.

## Verify recorded state

Read the approved `program.md` and ledger. Verify that:

- the recorded worktree exists and `git worktree list --porcelain` associates
  it with the recorded branch;
- the candidate record and log directories resolve to the recorded locations;
- when calibration is required, its separate record and log directories resolve
  to the recorded locations;
- when calibration has selected a unit, `calibration-decision.md` exists and
  identifies that unit with supporting evidence. If a candidate baseline exists,
  verify its recorded unit and evaluator log agree with the decision, and that
  later candidate records use the same unit. Missing or inconsistent evidence
  stops resumption; do not infer a unit from the best metric;
- the branch, `HEAD`, full worktree status, ledger, and logs match the run;
- only declared evaluator outputs are present. Unexpected tracked changes,
  undeclared untracked paths, a different branch, or an unexplained `HEAD` is a
  stop condition;
- the latest kept candidate commit (when a baseline exists), or the recorded
  initial commit during calibration, and every commit needed to interpret
  unfinished work exist with `git cat-file -e <sha>^{commit}`. A missing object
  is a stop condition.

Do not reset merely because a ledger entry names an older commit. If the state
cannot be reconciled without guessing, stop and report the exact mismatch.

## Reconcile an interrupted attempt

Before starting another evaluation, inspect logs and processes and reconcile
the first unfinished attempt in the applicable ledger:

- A completed log without a ledger record belongs to the commit named in its
  filename. Verify that object and append its result.
- An incomplete log without a record is a `crash` for that named commit once no
  evaluator process is running. Preserve the log and record the interruption.
- A clean committed `HEAD` with no log is unevaluated work. Evaluate it as the
  next attempt only when its origin and scope are clear.
- If a candidate discard or crash was not reset before interruption, reset only
  after the identity and clean-state checks above pass. Calibration measurements
  do not trigger candidate resets.

If calibration is required but the candidate ledger has no baseline record,
resume the pre-baseline initialization state. Reconcile its separate
calibration ledger and logs, preserve each `calibration:` description and
metrics, and finish or restart only within the approved calibration budget.
Calibration statuses do not select or retain code. Once a unit is selected,
record the decision in `calibration-decision.md`, then run the comparable
baseline into the candidate ledger. Do not reinterpret calibration as a
candidate improvement or silently combine it with a different iteration unit.

If the candidate ledger already has a baseline, initialization is complete. Do
not rerun calibration or baseline; resume candidate optimization from the
latest kept candidate commit with the selected unit fixed.

Check the original stop condition and remaining budget before another
evaluation. Resuming a session does not restart the run's budget.
