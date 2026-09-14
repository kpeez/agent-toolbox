# Autoresearch trial figures

Use this reference when a run should produce a figure of its attempts: at setup,
to declare the plot metadata, and at wrap-up, to draw it. The figure answers one
question — how the run's primary metric moved across attempts, and which
attempts the keep rule accepted. Every run draws it with the same script and the
same file; only the flags change.

The figure follows the `making-plots` skill. Read that skill before departing
from anything here, and name any departure in the metadata `note`.

## The two files

`trial-plot.json` in the candidate record directory holds the run's plotting
decisions. It is written once at setup, from the approved program, and is not
revised to flatter a result.

`<run>-trial-runs.jsonl` beside it is the plot input: one `metadata` record
carrying `trial-plot.json` plus provenance, then one `trial` record per ledger
record. It is **derived**. `scripts/ledger.py` regenerates it on every `append`
and `render` whenever `trial-plot.json` exists, and `ledger.py trials <run-dir>`
regenerates it on demand. Never hand-edit it; the ledger stays the source of
truth, and a plotting problem never blocks a ledger write — `append` warns on
stderr and still records the attempt.

Calibration records have their own record directory, so a calibration figure
needs its own `trial-plot.json` there. Do not merge the two ledgers.

## `trial-plot.json`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `run` | string | yes | the run tag; names the output file |
| `title` | string | yes | figure title: what is compared, on what data |
| `scope` | string | yes | data scope sentence for the footnote |
| `replication_unit` | string | yes | what a repeat is: `partition`, `seed`, `subject` |
| `primary_metric` | string | yes | metric key the keep rule compares; must be in `metrics` |
| `metrics` | object | yes | metric key → spec, below |
| `units_per_trial` | integer | no | repeats behind each attempt; shown on the axis label |
| `accept_delta` | number | no | the keep rule's margin; draws the acceptance bar |
| `accent` | hex string | no | colour for accepted attempts; defaults to the house accent |
| `note` | string | no | run-specific caveat appended to the footnote |

Each entry in `metrics`:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `label` | string | yes | axis label, including the statistic: `mean DIR @ FPIR 0.1` |
| `direction` | `maximize`\|`minimize` | yes | which way is better; drives the incumbent and the label |
| `limits` | `[low, high]` | no | the metric's domain; padding never leaves it |
| `spread` | string | no | metric key holding a symmetric ± whisker |
| `precision` | integer | no | decimals in value labels; inferred from the data otherwise |

Declare a metric here only if the program records it on every attempt under that
exact key. The keys are the ledger's declared run-specific metric keys; the
extraction command that fills them is the program's, and read-only.

Record the statistic you intend to plot, not the raw distribution: a summary
over the unit of replication (`..._mean`), and a second key for the display of
variability (`..._std`, `..._p10`). The ledger holds scalars; per-unit values
stay in the evaluator's own output.

## Declaring the run's figure

At setup, after the program is approved, write `trial-plot.json` and check it:

```bash
python3 <ledger.py> trials <record-dir>
python3 <plot_trials.py> <record-dir>/<run>-trial-runs.jsonl --validate
```

`--validate` needs no plotting library. It reports the run, the attempt counts
by status, and the declared metrics, and names the file and line of any schema
error. Run it at setup so a broken declaration fails then, not at wrap-up.

## Drawing the figure

```bash
python3 <plot_trials.py> <record-dir>/<run>-trial-runs.jsonl \
  --panel dir_at_fpir_0.1_mean --panel dir_at_fpir_0.1_p10 \
  --commits --out <artifact-dir>/<run>-trials.png
```

- `--panel METRIC` adds one panel, top to bottom, in the order given. The
  default is the primary metric alone. The primary metric's panel carries the
  incumbent step line and, when `accept_delta` is declared, the acceptance bar;
  every other panel gets a faint guide line, broken where an attempt has no
  value.
- `--commits` draws the evaluated commit under each attempt.
- `--labels keeps|all|none` controls value labels on the primary panel.
- `--accent HEX` overrides the metadata accent, for one figure only.
- `--width INCHES` widens the figure for a long run. The footnote wrap, panel
  heights, and reserved margins follow the width and the panel count.

The script requires `matplotlib`. Where the run's environment lacks it,
`uv run <plot_trials.py> ...` supplies it from the script's inline metadata.

Marks: a filled accent dot is an accepted attempt, an open neutral dot is one
that was not accepted, a dotted vertical rule is a crash, and `×` is a crash
that still produced a measurement. Colour carries one bit — accepted or not — so
set `accent` to the run's entity colour when the figure sits beside others.

## What the figure may not do

- Do not plot a metric the run did not record on every attempt under one key. A
  panel that mixes extraction commands or evaluation units is a false
  comparison; filter at summary time or leave it out.
- Do not plot calibration measurements beside candidate attempts. Calibration
  statuses do not select code, and the two ledgers are not comparable.
- Do not rescale, reorder, or drop attempts to make the climb look cleaner.
  Crashes and discards stay on the axis; they are the run's cost.
- `--commits` is a deliberate departure from the house rule that provenance
  lives in the summary file, not the figure. Use it when the run's chain of
  commits is the point; leave it off otherwise.
- `spread` is the house ±1 std whisker. It is wrong for a bounded, skewed
  metric, where a symmetric whisker runs outside the domain. Record a
  percentile key and give it its own panel instead, and say why in `note`.

## Worked example

```json
{
  "run": "2026-08-31-miewid-finetune-sweep",
  "title": "autoresearch sweep — MiewID fine-tune recipe search, fold-0 validation pool",
  "scope": "Fold-0 validation pool: 8 enrolled / 2 distractor subjects, 25 partitions per trial",
  "replication_unit": "partition",
  "units_per_trial": 25,
  "primary_metric": "dir_at_fpir_0.1_mean",
  "accept_delta": 0.01,
  "metrics": {
    "dir_at_fpir_0.1_mean": {
      "label": "mean DIR @ FPIR 0.1",
      "direction": "maximize",
      "limits": [0.0, 1.0]
    },
    "dir_at_fpir_0.1_p10": {
      "label": "10th-percentile partition DIR",
      "direction": "maximize",
      "limits": [0.0, 1.0]
    }
  },
  "note": "The lower panel shows the 10th-percentile partition rather than a ±1 std whisker: DIR is bounded on [0, 1] and strongly left-skewed early in the run, so a symmetric whisker would run above 1.0 and hide the tail the sweep closed."
}
```

The matching ledger call records both keys on every attempt:

```bash
python3 <ledger.py> append <record-dir> \
  --commit <full-sha> --status keep --description "exp000-baseline" \
  --metric dir_at_fpir_0.1_mean=0.838 --metric dir_at_fpir_0.1_p10=0.41
```

A crashed attempt records `key=null` for both, keeping its place on the axis.

Render the PNG and look at it before reporting the run. Collisions, clipped
marks, and a footnote that has fallen off the canvas are defects; a script that
exited zero is not a figure that is right.
