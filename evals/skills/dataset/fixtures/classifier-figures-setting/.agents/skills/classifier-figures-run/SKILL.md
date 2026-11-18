---
name: classifier-figures-run
description: "Use to regenerate the results table and the ROC curve from results/summary.csv."
---

# Regenerate the result figures

## When to use

After `results/summary.csv` changes, and before any figure goes into an update.

## Inputs

`results/summary.csv` with the columns `model`, `regime`, `tpr_fpr_0.1`, `tpr_fpr_0.01`, `auroc`, `accuracy`.

## Procedure

    uv run python figures.py --results results/summary.csv --out figures/

## Validity checks

- `figures/roc_curve.png` holds one curve for each model in the CSV.
- `figures/results_table.png` labels each row with the model and its `regime`.

## Known-good run

On the checked-in `results/summary.csv`, the command writes `results_table.png` and `roc_curve.png` and exits 0.

## Provenance

Record the CSV path and its git hash with each run.

## Gotchas

The `regime` column splits the fine-tuned rows from the zero-shot rows. The table labels depend on it.
