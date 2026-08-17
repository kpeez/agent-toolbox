---
name: autoresearch
description: Run an autonomous experiment loop that optimizes one metric through repeated small changes. Use when the user asks to autoresearch, run experiments overnight, iterate toward a target metric, or compare alternatives empirically. Co-authors a per-run program, runs a linear keep/discard loop in a dedicated worktree, and appends every result to a JSONL ledger.
---

# Autoresearch

You are an autonomous researcher. One linear loop: make a small change, commit
it, run the evaluator, keep the change if the metric improves, reset if it
does not. The rules that vary per run live in that run's `program.md`; this
skill defines the loop that never varies. The workflow follows
[Karpathy's autoresearch prompt](references/karpathy-program.md), generalized
to any repo and metric.

## Setup

Work with the user to set up the run. Create nothing until the program is
approved.

1. **Agree on a run tag**: propose a short date-based tag (e.g. `aug17`). The
   branch `autoresearch/<tag>` must not already exist — every run is fresh.
2. **Read the in-scope files** and agree on which paths are editable and which
   are read-only. The evaluator is always read-only.
3. **Co-author `program.md`** in chat, with exactly these fields:
   - **Goal**: the single primary metric and its direction (minimize or
     maximize).
   - **Evaluator**: the exact command to run, and the exact command that
     extracts the metrics from its output (e.g. a grep of `run.log`).
   - **Editable paths / read-only paths**.
   - **Per-experiment budget**: expected wall-clock per evaluation and the
     kill threshold (default: kill at twice the expected time).
   - **Soft constraints**: limits that may flex for a meaningful gain but must
     not blow up (e.g. memory).
   - **Stop condition**: a target metric value, an experiment count, or a
     wall-clock limit. The user may instead explicitly choose "run until
     interrupted" — write that choice down; never assume it.
   - **Run identity**: tag, branch, absolute worktree path, absolute record
     directory.
   - **Ledger record shape**: the run-specific keys inside `metrics` (see
     Logging results).
4. **Get explicit approval** of `program.md` in chat. Changing the program
   mid-run is not allowed; new rules mean a new approved program.
5. **Create the branch and its single worktree**:
   `git worktree add ../<repo>-autoresearch-<tag> -b autoresearch/<tag>`.
   The entire run happens in that one worktree. The user's checkout is never
   touched.
6. **Create the record directory** `docs/agents/autoresearch/<tag>/` via the
   primary repo and resolve its absolute path (the worktree has no
   `docs/agents` symlink). Write `program.md` there and create an empty
   `results.jsonl`. If the repo has no `docs/agents` symlink, use
   `<worktree>/.autoresearch/<tag>/` instead (untracked) and tell the user.
   The loop writes to the record directory and the worktree, nowhere else.
7. **Run the baseline**: experiment 0 is always the unmodified code. Its
   result is the first ledger line and the first best. If the baseline
   crashes, stop and report; there is nothing to improve against.

## Experimentation

Everything inside the editable paths is fair game: architecture,
hyperparameters, algorithms, data handling, sizes, the training or serving
loop itself.

You cannot:

- modify the evaluator or any read-only path — its parsed output is the
  ground truth, and only it decides keep or discard;
- add dependencies, unless the program allows it;
- exceed a soft constraint dramatically, even for a better metric.

**Simplicity criterion**: all else equal, simpler wins. Weigh complexity cost
against improvement size. A tiny gain that adds twenty ugly lines is not
worth keeping; an equal result from deleting code is a great outcome.

## Output format

Run the evaluator exactly as the program states, redirecting everything:
`<evaluator command> > run.log 2>&1`. Never tee or stream evaluator output
into your context. `run.log` lives in the worktree root and is overwritten
every experiment. Extract metrics with the program's extraction command.
Empty extraction output means the run crashed — read `tail -n 50 run.log`
for the reason.

## Logging results

Append exactly one line per experiment to `results.jsonl` — crashes included —
and never rewrite, reorder, or delete existing lines. Core keys are fixed;
run-specific measurements go inside `metrics` under the keys the program
names (`null` when a crash produced no measurement):

```json
{"id": 0, "commit": "a1b2c3d", "status": "keep", "description": "baseline", "metrics": {"val_bpb": 0.9979, "peak_vram_gb": 44.0}}
```

`status` is `keep`, `discard`, or `crash`. After each append, regenerate
`summary.md` next to the ledger: a markdown table of every experiment plus
the current best. Write a small run-specific render script during setup if
that helps; the skill ships none. The ledger, not the summary, is the source
of truth.

## The experiment loop

LOOP:

1. Start from the last best commit with a clean worktree.
2. Pick one idea and make the smallest change that tests it.
3. Commit. The commit hash is the experiment's identity — one idea per
   commit, no bundling.
4. Run the evaluator (see Output format).
5. Extract the metrics. On a crash: if the cause is trivial (a typo, a
   missing import), fix and re-run; if the idea itself is broken, log
   `crash`, reset, and move on. Give up on an idea after a few fix attempts.
6. Append the ledger line and regenerate `summary.md`.
7. Improved → `keep`: the branch simply advances. Equal or worse →
   `discard`: `git reset --hard` back to the last best commit. Discarded
   commits survive as hashes in the ledger.
8. Check the stop condition. Unmet → go to 1.

If an evaluation exceeds the kill threshold, kill it and log it as a crash.
Do not pause mid-loop to ask whether to continue — the user may be asleep and
expects you to run until the stop condition fires (or indefinitely, when the
program says run until interrupted). Out of ideas means think harder: re-read
the in-scope files, revisit near-misses, combine partial wins, try something
structural.

## Wrap-up

When the stop condition fires or the user interrupts, regenerate `summary.md`,
then report: best commit and its metrics versus baseline, experiments
attempted and kept, branch name, worktree path, and record directory. Leave
the branch and worktree in place — merging, publishing, or discarding the
result is the user's call, never yours.
