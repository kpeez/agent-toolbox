---
name: research-context
description: "Use before any analysis, experiment, or claim about the text classifier benchmark results."
---

# Text classifier benchmark context

## Data

`results/summary.csv` holds held-out metrics for each model on one synthetic benchmark. One row is one model in one regime.

## Variables

- `model`: the classifier size, `tiny`, `base`, `large`, or `distilled`.
- `regime`: `fine-tuned` or `zero-shot`.
- `tpr_fpr_0.1`, `tpr_fpr_0.01`: true-positive rate at that false-positive rate.
- `auroc`, `accuracy`: the other two metrics.

## How the data arose

Each model ran on the same held-out test split. Zero-shot rows use no task data for training.

## Known confounds

Zero-shot and fine-tuned rows differ in training data and in model size.

## Conventions

Report TPR at FPR 0.01 first. Project convention.

## Commands

    uv run python figures.py --results results/summary.csv --out figures/

## Procedure skills

- `classifier-figures-run`: live.

## Open questions

None recorded.
