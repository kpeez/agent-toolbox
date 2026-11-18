import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

METRICS = ["tpr_fpr_0.1", "tpr_fpr_0.01", "auroc", "accuracy"]


def load(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def draw_table(rows, out):
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.axis("off")
    cells = [[row[m] for row in rows] for m in METRICS]
    labels = [f"{row['model']} ({row['regime']})" for row in rows]
    ax.table(cellText=cells, rowLabels=METRICS, colLabels=labels, loc="center")
    fig.savefig(out / "results_table.png", dpi=150)


def draw_roc(rows, out):
    fig, ax = plt.subplots()
    for row in rows:
        ax.plot(
            [0.01, 0.1],
            [float(row["tpr_fpr_0.01"]), float(row["tpr_fpr_0.1"])],
            label=row["model"],
        )
    ax.set_xscale("log")
    ax.legend()
    fig.savefig(out / "roc_curve.png", dpi=150)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path("results/summary.csv"))
    parser.add_argument("--out", type=Path, default=Path("figures"))
    args = parser.parse_args()
    args.out.mkdir(exist_ok=True)
    rows = load(args.results)
    draw_table(rows, args.out)
    draw_roc(rows, args.out)


if __name__ == "__main__":
    main()
