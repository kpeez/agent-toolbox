---
name: verify-eval-budget
description: Model-check the eval-batch budget in evals/skills/run_eval.py (Batch.reserve, Batch.release, spend, finished, prepare, and a resume after a kill) with TLC, and replay every model state on the real code. Use when a change touches those functions, the run.json fields they read, or how execute hands runs to workers, or when the check fails.
paths:
  - evals/skills/run_eval.py
---

# Verify the eval-batch budget

## The rules

| Rule | Plain sentence | Harm when it breaks |
| --- | --- | --- |
| `CapSafe` | Known spend, plus the stop amount for each attempt with no known cost and for each launch in flight, never passes `--max-total-usd`. | A batch can spend more real money than its cap. |
| `NoFalseStop` | `Batch.reserve` stops the batch for budget only when the next launch would pass the cap. | A batch stops with budget left and gives a partial, biased sample. |

## Run it

From the repository root:

```sh
uv run .agents/skills/verify-eval-budget/scripts/check.py
```

It needs uv and mise. It takes TLC and Java from `TLA2TOOLS` and `JAVA`, or
installs the statechart skill's pins through
`.github/scripts/statechart_tlc.py`. It takes about 20 seconds. CI runs it
in the `eval-budget-model-check` job of `.github/workflows/checks.yml`. It
exits 0 only when all three stages pass:

1. `now`: TLC checks `EvalBudget.tla` on `EvalBudget.cfg`, the current code.
   Both rules hold.
2. Past-bug variants: each one must break its rule, so each rule can fail.
   - `in-flight-counter` (`InFlight = "counter"` and
     `MoveAside = "prepare"`, the code before `3df0eca`) breaks
     `NoFalseStop`: a launch that saved run.json with no cost counts twice,
     once in spend and once in flight.
   - `move-aside-in-prepare` (`MoveAside = "prepare"`, the code before
     `9fb690e`) breaks `CapSafe`: on a resume, spend skips a stale folder
     that a worker reserved but has not moved aside yet.
3. Real code: TLC saves the state graph of `Replay.cfg`. In each state, each
   `Reserve`, `Prepare`, `Release`, and `Resume` step runs on the real
   `run_eval` functions in a temporary `--out` folder. The real next states
   must equal the model's next states. A real step that raises, for
   example after a signature change, also fails this stage.

`--no-variants` skips stage 2. `--no-replay` skips stage 3.

## Read a result

Read every TLC result with the `statechart` skill. Give it `EvalBudget.tla`,
a config, `view.mjs` as the view, and an `--out` folder in your scratch
folder. `Chart.cfg` is small enough for a full chart of the current code.
For a past-bug variant, copy `Chart.cfg` to scratch and set `InFlight` and
`MoveAside` as stage 2 lists. The report then gives the bug path in plain
words.

## How the model maps to the code

Each action is one indivisible step in the code:

| Action | Code | Lock |
| --- | --- | --- |
| `Reserve(w, r)` | `execute.one`: `finished(run)`, then `Batch.reserve(run)`: move a stale folder to `interrupted/`, `spend`, the cap check, `active.add` | `Batch.lock` for `reserve`. `finished` reads only this run's folder, and no other worker writes it, so it joins the step. |
| `Prepare(w)` | `prepare` (and `se.materialize`, which writes no run.json) | none |
| `LaunchStart(w)` | the first `save_json` of run.json in `launch`, with `cost_usd` null | none |
| `LaunchEnd(w)` | the last `save_json` in `launch`; `"started"` stands for `launch` raising | none |
| `Release(w)` | `Batch.release` with the run's record, or the stand-in record of the `except` branch | `Batch.lock` |
| `Resume` | the process dies at any step, and a rerun builds a new `Batch` from the same `--out` | none |

`spend` reads files under the lock, but `launch` writes run.json outside it.
That is safe to treat as one step: in the current code, each file that
another worker writes during a `reserve` is in `Batch.active`, and `spend`
skips it. `save_json` replaces a file in one step, so a read never sees half
a file. Only `reserve` moves a run folder, under the lock, so no file leaves
`runs/` between the two `glob` calls of `spend`.

Assumptions: a launch costs at most the stop amount (`launch_argv` passes it
as `--max-cost-usd`). Workers take plan items in any order, which includes
the pool's order.

## Bounds

- `EvalBudget.cfg`: 3 workers, 3 runs, 2 kills and resumes, caps from 1 to 8
  with a stop amount of 2 and a known cost of 1, and all four launch ends.
  About 614,000 states.
- `Replay.cfg`: 2 workers, 2 runs, 1 resume, caps 1, 4, and 5. About 2,800
  states and 4,000 real steps.
- Not covered: `canary`, `violations` in a record, a known cost with an
  `error` (it only counts toward the errors stop), `prepare` raising, a cost
  over the stop amount, and the launch writes themselves (stage 3 writes
  run.json in their place).

## Coverage

`Batch.reserve`, `Batch.release`, `Batch.halt`, `Batch.__init__`, `spend`,
`finished`, `prepare`, `execute.one`, and the two `save_json` calls of
`launch` in `evals/skills/run_eval.py`. The
run.json fields read: `cost_usd`, `ended_at`, `api_error`, `error`.

Sync commit: `325ba0e`. At that commit the model describes the code.

## When a change touches the covered code

1. Run the check before and after the change.
2. A `now` or variant failure is in the model. A `real code` failure prints
   a model state, the step, and what only the real code or only the model
   reaches.
3. Tell a real bug from a modeling error: build the printed state in a
   scratch `--out` folder and call the real function. When the real result
   breaks a rule, it is a bug in the change. When the change is intended,
   the model is out of date: update the action in `EvalBudget.tla`, the
   table above, and stage 3 in `scripts/check.py` in the same change.
4. Never weaken a rule or remove a variant only to make the check pass.
5. After you confirm that the model describes the code, set the sync commit
   above to the commit you checked.
