Synthetic text classifier benchmark comparing four models across two evaluation
regimes. `results/summary.csv` holds summary metrics across splits, and
`figures.py` draws the results table and the ROC curves into `figures/`:

    uv run python figures.py --results results/summary.csv --out figures/
