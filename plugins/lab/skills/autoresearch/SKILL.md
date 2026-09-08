---
name: autoresearch
description: Run an autonomous experiment loop that optimizes one metric through repeated small changes. Use when the user asks to autoresearch, run experiments overnight, iterate toward a target metric, or compare alternatives empirically. Co-authors a per-run program, runs a linear keep/discard loop in a dedicated worktree, and appends every result to a JSONL ledger.
---

# Autoresearch

Run one linear experiment loop: make a small change, commit it, evaluate that
exact commit, then keep or discard it according to the approved program. Rules
that vary live in the run's `program.md`; this skill defines the stable loop.
The historical [Karpathy prompt](references/karpathy-program.md) is provenance
only. Its TSV, branch, fixed budget, and infinite-loop rules are not active.

## Setup

Work with the user to define the run. Create nothing until the program is
approved.

1. **Agree on a run tag.** Use a short date-based tag. Verify that the new
   `autoresearch/<tag>` branch and dedicated worktree do not already exist.
2. **Read the in-scope files.** Agree on editable and read-only paths. The
   evaluator and metric extraction are always read-only.
3. **Co-author `program.md`** with:
   - **Goal:** one primary metric and whether to minimize or maximize it.
   - **Evaluator:** exact evaluation and metric-extraction commands.
   - **Editable paths / read-only paths.**
   - **Output paths:** absolute record and log directories plus every path the
     evaluator may create. Prefer outputs outside the worktree or paths already
     ignored by the target repository. If a new in-worktree path is needed,
     make the ignore-file change explicit and keep it within approved editable
     scope; do not silently change repository or shared Git ignore settings.
   - **Per-attempt budget:** expected duration and kill threshold. Twice the
     expected duration is a reasonable default.
   - **Soft constraints:** limits that may flex for a meaningful gain.
   - **Tie policy:** normally discard equal primary metrics. Allow an equal
     result for a simpler implementation only when the program explicitly says
     how to judge that tradeoff.
   - **Stop condition:** target value, attempt count, wall-clock limit, or an
     explicit `run until interrupted`. Never assume an indefinite run.
   - **Run identity:** tag, branch, absolute worktree path, primary checkout,
     record directory, log directory, and absolute path to `scripts/ledger.py`.
   - **Ledger metrics:** the run-specific keys stored under `metrics`.
   Resolve the proposed record and log locations from actual filesystem state
   before approval; a missing or unwritable path is not permission to pick an
   unapproved fallback later.
4. **Get explicit approval** of `program.md`. New rules require a new approved
   program; do not revise an active run in place.
5. **Create the branch and single worktree:**
   `git worktree add ../<repo>-autoresearch-<tag> -b autoresearch/<tag>`.
   Record `git -C <worktree> status --short --untracked-files=all` before the
   baseline. Stop if it contains unexpected state.
6. **Create the approved records.** Prefer the resolved primary checkout's
   `docs/agents/autoresearch/<tag>/` when available; an ignored
   `.autoresearch/<tag>/` or outside-worktree directory is also valid when
   chosen in the approved program. Do not assume a linked worktree lacks or
   shares `docs/agents`. Recheck the approved paths, write the approved
   `program.md`, and create an empty `results.jsonl` and log directory without
   overwriting existing records.
7. **Run the baseline.** Attempt 0 evaluates unmodified code. Commit identity,
   log, and ledger record follow the same rules as every later attempt. The
   baseline is the first `keep`. If it crashes, record the crash and stop.

## Resume an approved run

Resume from observed state, not from an assumed ledger position.

1. Read the approved program and ledger. Verify the recorded worktree exists,
   `git worktree list --porcelain` associates it with the recorded branch, and
   the record and log directories resolve to the recorded locations.
2. Inspect the branch, `HEAD`, full worktree status, ledger, and logs. Permit
   only declared evaluator outputs. Unexpected tracked changes, undeclared
   untracked paths, a different branch, or an unexplained `HEAD` is a stop
   condition.
3. Find the latest kept commit in the ledger and verify that both it and every
   commit needed to interpret unfinished work exist with
   `git cat-file -e <sha>^{commit}`. A missing object is a stop condition.
4. Reconcile an interrupted attempt before starting another:
   - A completed log without a ledger record belongs to the commit named in its
     filename. Verify that object and append the attempt's result.
   - An incomplete log without a record is a `crash` for that named commit once
     no evaluator process is running. Preserve the log and record the
     interruption.
   - A clean committed `HEAD` with no log is unevaluated work. Evaluate it as
     the next attempt only when its origin and scope are clear.
   - If a recorded discard or crash was not reset before interruption, reset
     only after the identity and clean-state checks below pass.
5. If the state cannot be reconciled without guessing, stop and report the
   exact mismatch. Never reset merely because a ledger entry names an older
   commit.
6. Check the original stop condition and remaining budget before another
   evaluation. Resuming a session does not restart the run's budget.

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

Every evaluator invocation is one attempt with one committed code state, one
log, and one ledger record, including crashes and retries.

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
fix, commit it, then evaluate the new commit under a new ID and log. Never reuse
the previous commit, ID, or log for a retry. If the idea itself is broken,
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

1. Start from the latest kept commit with a clean worktree. Before editing or
   resetting, inspect `git status --short --untracked-files=all`. Declared,
   ignored evaluator outputs may remain; anything else stops the loop.
2. Pick one idea and make the smallest change that tests it.
3. Commit the code that will be evaluated. The commit is the experiment's
   identity.
4. Evaluate and record the attempt as described above.
5. Keep an improved metric. Keep an equal metric only when the approved tie
   policy allows the demonstrated simplification. Otherwise discard it.
6. After a discard or a crash that will not be retried, verify the expected
   worktree and branch, confirm the status contains no unexpected paths, and
   verify the target kept commit with `git cat-file -e <sha>^{commit}`. Only then
   reset the experiment branch to that commit. Never start the next idea from
   an abandoned crashed candidate. The attempt remains identified in the ledger.
7. Check the stop condition. If it is unmet, continue.

When an evaluation exceeds the kill threshold, terminate it and record a crash.
Do not pause mid-loop merely to ask whether to continue. Stop for the approved
condition, user interruption, unsafe or unreconciled state, or a missing
required capability. When ideas run thin, revisit in-scope code and retained
results within the remaining budget; do not broaden scope.

## Wrap-up

When the run stops, render `summary.md` and report the latest kept commit and
metrics versus baseline, attempts and keeps, stop reason, branch, worktree,
record directory, and any unreconciled state. Leave the branch and worktree in
place. Merging, publishing, or discarding the result remains the user's choice.
