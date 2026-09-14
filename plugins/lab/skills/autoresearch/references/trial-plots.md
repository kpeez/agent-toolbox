# Autoresearch progress plot

Use one shared `scripts/plot_trials.py` for the standard progress plot across
runs. It reads the candidate `results.jsonl` directly and plots only the metric
the approved program optimizes. Do not copy or fork the standard renderer into
each run. Additional visualizations and their scripts belong in that run's
autoresearch folder; they supplement this plot.

## Declare the objective

At setup, copy the objective key and direction from the approved program into
`trial-plot.json` in the candidate record directory. Add its display label
(including units or the statistic) and a title naming the run and data. Do not
infer the objective from whichever metric looks best. The program owns the
objective; this small file supplies the shared renderer's configuration.

```json
{
  "metric": "val_bpb",
  "label": "Validation bits per byte",
  "direction": "minimize",
  "title": "2026-09-14-training-throughput — fixed validation set",
  "scope": "Same evaluation budget per candidate; one evaluation per attempt."
}
```

`metric`, `label`, `direction`, and `title` are required. `scope` is an optional
short note about evaluation budget, data, or replication. Every non-crashed
attempt must record a finite value under the selected metric key. A crash can
record `null` or lack a measurement. Other ledger metrics remain available for
run-specific analysis but do not create additional panels.

## Render

```bash
python3 <plot_trials.py> <candidate-record-dir> --validate
uv run <plot_trials.py> <candidate-record-dir>
```

Validation needs no plotting dependencies. Rendering uses matplotlib, supplied
by the script's inline dependency metadata when using `uv run`. Reuse the run's
environment when matplotlib is already available. Declare the renderer and
output path in the approved program. The default output is `progress.png` in
the candidate record directory; `--out <path>.png` selects another approved
location and `--width <inches>` adjusts the layout.

The single plot shows experiment number against the optimization metric, muted
discarded points, prominent kept points, and the running best among kept
experiments. Every kept point is labeled with its `expNNN-slug`; older ledger
descriptions are preserved as labels rather than rewritten. Crashes retain
their position, with unmeasured crashes marked along the bottom rather than
assigned an invented metric value. There are no secondary panels, acceptance
thresholds, or commit-label rows.

Refresh at the program's reporting checkpoints and at wrap-up, after the ledger
record is complete. A plotting failure must not trigger a repeated evaluator
invocation or undo a recorded attempt. Report that the plot could not refresh
and do not present an older PNG as current. Inspect the rendered PNG for label
collisions, clipping, and legibility before reporting it.

Keep calibration separate: its evaluation horizons differ and its `keep`
status means a measurement completed, not a candidate improvement. Calibration
and uncertainty-specific figures belong in run-local analysis. This standard
plot shows recorded objective values, not confidence intervals; name any
aggregation in the metric label and record replication details in `scope`.

## Existing runs

Do not rewrite old ledgers, names, or approved programs. When adopting this
renderer, explicitly replace the old multi-metric plot configuration with the
single approved objective above. Old `*-trial-runs.jsonl` files are no longer
read or regenerated; leave existing artifacts untouched. The ledger's `append`
and `render` commands only maintain `results.jsonl` and `summary.md`.
