# Autoresearch setup and program approval

Use this reference only when starting a new run. The root skill owns the
experiment loop; this file defines the approval-time contract.

## Define the run

Work with the user to define the run before creating branches, worktrees, or
records. Reuse an already-approved program when resuming or continuing an
authorized run; do not repeat the interview or revise its rules in place.

Agree on:

- a short date-based run tag, and that the `autoresearch/<tag>` branch and
  dedicated worktree do not already exist;
- the editable and read-only paths. The evaluator and metric extraction are
  always read-only;
- one primary metric and whether to minimize or maximize it;
- exact evaluator and metric-extraction commands;
- absolute candidate record and log directories plus every path the evaluator
  may create;
- separate absolute calibration record and log directories when calibration is
  required. Calibration must not share `results.jsonl` with candidate records,
  so the candidate ledger starts with the comparable baseline and its latest
  `keep` remains the best candidate state;
- expected duration and a kill threshold for each evaluation;
- soft constraints, tie policy, and a stop condition (target, attempt count,
  wall-clock limit, or an explicitly approved `run until interrupted`);
- the run identity: tag, branch, absolute worktree path, primary checkout,
  candidate and (when needed) calibration record and log directories, and
  absolute path to `scripts/ledger.py`;
- the run-specific keys stored under `metrics`.

Resolve record and log locations from actual filesystem state before approval. A
missing or unwritable path is not permission to choose an unapproved fallback.
Prefer evaluator outputs outside the worktree or paths already ignored by the
target repository. If a new in-worktree path is needed, make the ignore-file
change explicit and keep it within approved editable scope.

## Define the iteration unit

The iteration unit is the amount of work each candidate receives before its
result can support a keep/discard decision. It may be a step or token budget,
one or more epochs, a data subset, a time horizon, or another workload-specific
evaluation horizon. Seek the best reliable signal per unit of elapsed time or
compute, not simply the shortest run. A full training run may be too expensive;
one epoch may be too noisy or too early to distinguish changes.

Use prior evidence or a simple bounded pilot when it can establish a useful
unit. If the choice remains unclear, the calibration is the first experiment,
before the comparable optimization baseline. The approved program must state:

- a small set of plausible units and a bound on calibration evaluations,
  elapsed time, or compute;
- a fixed evaluator, data boundary, and any seed or repeat policy used to
  compare units;
- selection criteria covering cost, variability, and whether conclusions track
  the intended objective. Choose a practical unit supported by the evidence;
  do not claim a global optimum;
- the kill threshold and stop condition for calibration, including what counts
  as insufficient signal;
- how calibration records are kept separate from candidate improvements.

Change only the workload horizon during calibration. Do not tune the evaluator
to favor a unit or candidate. Record each invocation with the existing
`scripts/ledger.py` in the approved calibration record directory, with a
distinct log and a description prefixed `calibration:`. Use the existing ledger
metric keys for elapsed cost, objective, variability, or related evidence; do
not extend the ledger runtime merely to add a phase field. A successful
measurement may use status `keep`, which means the measurement completed, not
that the unit won an optimization comparison. A crash is recorded as `crash`.
The separate calibration ledger is not a candidate ledger and its statuses do
not select or retain code.

Write the selected unit and its supporting evidence to `calibration-decision.md`
in the approved calibration record directory without revising the approved
program. Then establish an unmodified baseline using the same evaluator, data
boundary, and unit. Record it as the first optimization `keep` in the candidate
ledger. Hold the unit fixed for candidate evaluations. Recalibrate only with comparable evidence
under an approved program, and do not mix incompatible measurements when
comparing candidates.

Record the selected unit in each baseline and candidate record using declared
run-specific metric keys (for example, `evaluation_steps=500`). This lets resume
checks verify comparability against the decision and actual evaluator logs.

## Approve and create the run

Get explicit approval of the complete `program.md`, including the calibration
plan when one is needed. New rules require a new approved program. Then:

1. Create the single worktree:
   `git worktree add ../<repo>-autoresearch-<tag> -b autoresearch/<tag>`.
2. Record `git -C <worktree> status --short --untracked-files=all` before any
   baseline or calibration. Stop if it contains unexpected state.
3. Recheck the approved paths. Create directories as needed, write the
   approved `program.md`, and create an empty candidate `results.jsonl` and log
   directory. When required, create a separate empty calibration
   `results.jsonl`, log directory, and (after selection) `calibration-decision.md`.
   Never overwrite existing records.
4. Run calibration first when the program requires it. Use its declared
   selection rule and record the selected unit before running the unmodified
   baseline. Otherwise run the baseline at the approved unit. If the baseline
   crashes, record it and stop.

Default records live at the resolved primary checkout's
`docs/agents/autoresearch/<tag>/` unless the project or user specifies another
location. This may be tracked, ignored, or reached through an existing symlink.
Do not assume a linked worktree lacks or shares `docs/agents`.
