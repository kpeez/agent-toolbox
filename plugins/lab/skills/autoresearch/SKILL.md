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
     extracts the metrics from its output (e.g. a grep of the experiment
     log).
   - **Editable paths / read-only paths**.
   - **Per-experiment budget**: expected wall-clock per evaluation and the
     kill threshold (default: kill at twice the expected time).
   - **Soft constraints**: limits that may flex for a meaningful gain but must
     not blow up (e.g. memory).
   - **Stop condition**: a target metric value, an experiment count, or a
     wall-clock limit. The user may instead explicitly choose "run until
     interrupted" — write that choice down; never assume it.
   - **Run identity**: tag, branch, absolute worktree path, absolute record
     directory, and the absolute path of this skill's `scripts/ledger.py`.
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
`<evaluator command> > logs/<id>.log 2>&1`, where `<id>` is the experiment
number. Never tee or stream evaluator output into your context. `logs/` lives
in the worktree root, untracked — it survives every reset and lasts as long
as the worktree, so near-misses keep their raw output for later mining.
Extract metrics with the program's extraction command. Empty extraction
output means the run crashed — read `tail -n 50 logs/<id>.log` for the
reason.

## Logging results

Log exactly one record per experiment — crashes included — with this skill's
ledger script, using the path recorded in the program:

```bash
python3 <ledger.py> append <record-dir> \
  --commit a1b2c3d --status keep --description "baseline" \
  --metric val_bpb=0.9979 --metric peak_vram_gb=44.0
```

One command assigns the next id, appends one JSON line to `results.jsonl`,
and regenerates `summary.md` (a markdown table of every experiment with the
current best marked). `status` is `keep`, `discard`, or `crash`. Core keys
are fixed; run-specific measurements are `--metric key=value` pairs under the
keys the program names (`key=null` when a crash produced no measurement).
The ledger is append-only — the script has no update or delete verb, and you
must never rewrite, reorder, or delete its lines by hand. A wrong record is
corrected by appending a superseding one. The ledger, not the summary, is
the source of truth; `ledger.py render <record-dir>` rebuilds the summary
alone.

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
6. Log the experiment with one `ledger.py append` command (see Logging
   results).
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

When the stop condition fires or the user interrupts, regenerate `summary.md`
(`ledger.py render`), then report: best commit and its metrics versus baseline, experiments
attempted and kept, branch name, worktree path, and record directory. Leave
the branch and worktree in place — merging, publishing, or discarding the
result is the user's call, never yours.
