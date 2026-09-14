#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib>=3.8"]
# ///
"""Plot one autoresearch run from its trial-runs file.

  plot_trials.py TRIALS_JSONL --out FIGURE.png [--panel METRIC ...] [--commits]
  plot_trials.py TRIALS_JSONL --validate

The input is `<run>-trial-runs.jsonl`, written by `ledger.py trials`: one
`record: metadata` line followed by one `record: trial` line per attempt. The
metadata line carries every run-specific plotting decision -- display labels,
metric direction, bounded domains, the acceptance delta, the data scope -- so
one command draws any run and only the flags below change between figures.

Panels are drawn top to bottom in `--panel` order; the default is the run's
primary metric alone. The primary metric's panel also carries the incumbent
step line and, when the metadata declares `accept_delta`, the acceptance bar.

Colour carries one bit -- accepted vs not -- so a run may set its own `accent`
and stay in the colour system of the figures beside it.
"""

from __future__ import annotations

import argparse
import json
import math
import textwrap
from pathlib import Path
from typing import Any

# House style, mirrored from the making-plots skill's style module so this
# script runs standalone. Nothing else here sets rcParams.
NEUTRAL = "#6b7280"
ACCENT = "#d9541e"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
RULE_GRAY = "#d9d8d3"
SURFACE = "#fcfcfb"

STATUSES = ("keep", "discard", "crash")
DIRECTIONS = ("maximize", "minimize")
METADATA_FIELDS = ("run", "title", "scope", "replication_unit", "primary_metric")

KEEP_SIZE = 7.0
OTHER_SIZE = 5.2
# Footnote characters per inch of figure width; 120 at the 9 in house default.
FOOTNOTE_CHARS_PER_INCH = 13
AXIS_LABEL_CHARS = 22
FOOTNOTE_LINE_INCHES = 0.17


def fail(message: str) -> None:
    raise SystemExit(f"plot_trials: {message}")


def require_number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f"{where}: expected a number, got {value!r}")
    if not math.isfinite(float(value)):
        fail(f"{where}: {value!r} is not finite; record null for a missing measurement")
    return float(value)


def check_metadata(metadata: dict[str, Any], where: str) -> None:
    for field in METADATA_FIELDS:
        if not isinstance(metadata.get(field), str) or not metadata[field].strip():
            fail(f"{where}: metadata needs a non-empty {field!r}")
    metrics = metadata.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        fail(f"{where}: metadata needs a non-empty 'metrics' object")
    for key, spec in metrics.items():
        if not isinstance(spec, dict):
            fail(f"{where}: metrics[{key!r}] must be an object")
        if not isinstance(spec.get("label"), str) or not spec["label"].strip():
            fail(f"{where}: metrics[{key!r}] needs a non-empty 'label'")
        if spec.get("direction") not in DIRECTIONS:
            fail(f"{where}: metrics[{key!r}].direction must be one of {', '.join(DIRECTIONS)}")
        limits = spec.get("limits")
        if limits is not None:
            if not isinstance(limits, list) or len(limits) != 2:
                fail(f"{where}: metrics[{key!r}].limits must be [low, high]")
            low = require_number(limits[0], f"{where}: metrics[{key!r}].limits[0]")
            high = require_number(limits[1], f"{where}: metrics[{key!r}].limits[1]")
            if low >= high:
                fail(f"{where}: metrics[{key!r}].limits must increase, got {limits}")
        spread = spec.get("spread")
        if spread is not None and not isinstance(spread, str):
            fail(f"{where}: metrics[{key!r}].spread must be the metric key holding the spread")
        precision = spec.get("precision")
        if precision is not None and (
            isinstance(precision, bool) or not isinstance(precision, int) or precision < 0
        ):
            fail(f"{where}: metrics[{key!r}].precision must be a non-negative integer")
    if metadata["primary_metric"] not in metrics:
        fail(f"{where}: primary_metric {metadata['primary_metric']!r} is not in 'metrics'")
    if metadata.get("accept_delta") is not None:
        require_number(metadata["accept_delta"], f"{where}: accept_delta")
    units = metadata.get("units_per_trial")
    if units is not None and (isinstance(units, bool) or not isinstance(units, int)):
        fail(f"{where}: units_per_trial must be an integer count of {metadata['replication_unit']}s")
    for field in ("accent", "note"):
        if metadata.get(field) is not None and not isinstance(metadata[field], str):
            fail(f"{where}: {field!r} must be a string")


def check_trial(trial: dict[str, Any], metadata: dict[str, Any], where: str) -> None:
    if not isinstance(trial.get("id"), int) or isinstance(trial["id"], bool):
        fail(f"{where}: trial needs an integer 'id'")
    if trial.get("status") not in STATUSES:
        fail(f"{where}: status must be one of {', '.join(STATUSES)}")
    metrics = trial.get("metrics") or {}
    if not isinstance(metrics, dict):
        fail(f"{where}: 'metrics' must be an object")
    # Only declared keys are plotted, so only they must be numeric; the ledger
    # may carry other keys of any type.
    declared = set(metadata["metrics"])
    declared |= {
        spec["spread"] for spec in metadata["metrics"].values() if spec.get("spread")
    }
    for key in declared & set(metrics):
        if metrics[key] is not None:
            require_number(metrics[key], f"{where}: metrics[{key!r}]")


def load(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Read and validate the trial-runs file. Every error names its line."""
    if not path.is_file():
        fail(f"trial-runs file not found: {path}")
    numbered = [
        (number, line)
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if line.strip()
    ]
    if not numbered:
        fail(f"{path} is empty")
    records = []
    for number, line in numbered:
        try:
            records.append((number, json.loads(line)))
        except json.JSONDecodeError as error:
            fail(f"{path}:{number}: {error}")
    for number, record in records:
        if not isinstance(record, dict):
            fail(f"{path}:{number}: each line must be a JSON object")
    first_line, metadata = records[0]
    if metadata.get("record") != "metadata":
        fail(f"{path}:{first_line}: the first line must be the 'metadata' record")
    check_metadata(metadata, f"{path}:{first_line}")
    trials: list[dict[str, Any]] = []
    for number, record in records[1:]:
        if record.get("record") != "trial":
            fail(f"{path}:{number}: expected a 'trial' record after the metadata line")
        check_trial(record, metadata, f"{path}:{number}")
        if trials and record["id"] <= trials[-1]["id"]:
            fail(f"{path}:{number}: trial ids must increase, got {record['id']}")
        trials.append(record)
    return metadata, trials


def value_of(trial: dict[str, Any], key: str) -> float | None:
    raw = (trial.get("metrics") or {}).get(key)
    return None if raw is None else float(raw)


def drawn(trials: list[dict[str, Any]], panels: list[str], status: str) -> bool:
    """Whether a mark of this status actually appears on a drawn panel."""
    return any(
        value_of(trial, key) is not None
        for trial in trials
        if trial["status"] == status
        for key in panels
    )


def incumbent_series(
    trials: list[dict[str, Any]], key: str, direction: str
) -> list[tuple[int, float]]:
    """Best value among accepted attempts, as of each attempt."""
    better = max if direction == "maximize" else min
    best: float | None = None
    series = []
    for trial in trials:
        current = value_of(trial, key)
        if trial["status"] == "keep" and current is not None:
            best = current if best is None else better(best, current)
        if best is not None:
            series.append((trial["id"], best))
    return series


def panel_points(
    trials: list[dict[str, Any]], key: str, spread_key: str | None
) -> list[tuple[dict[str, Any], float, float]]:
    """(trial, value, spread) for every attempt with a value on this metric."""
    points = []
    for trial in trials:
        current = value_of(trial, key)
        if current is None:
            continue
        spread = value_of(trial, spread_key) if spread_key else None
        points.append((trial, current, abs(spread) if spread is not None else 0.0))
    return points


def decimals(trials: list[dict[str, Any]], key: str, spec: dict[str, Any]) -> int:
    """Decimals for value labels: the run's choice, else the most any value uses."""
    if spec.get("precision") is not None:
        return int(spec["precision"])
    most = 0
    for trial in trials:
        current = value_of(trial, key)
        if current is None:
            continue
        text = repr(current)
        if "e" in text or "E" in text:
            return 6
        most = max(most, len(text.partition(".")[2].rstrip("0")))
    return min(most, 6)


def apply_style() -> None:
    import matplotlib

    matplotlib.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 9,
            "text.color": TEXT_PRIMARY,
            "axes.labelcolor": TEXT_SECONDARY,
            "axes.labelsize": 9,
            "xtick.color": TEXT_SECONDARY,
            "ytick.color": TEXT_SECONDARY,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "xtick.major.size": 3,
            "ytick.major.size": 3,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "axes.edgecolor": RULE_GRAY,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "axes.axisbelow": True,
            "axes.titlesize": 10,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.titlepad": 6,
            "figure.titlesize": 11,
            "figure.titleweight": "bold",
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "legend.frameon": False,
            "legend.fontsize": 8,
            "lines.linewidth": 1.4,
            "savefig.dpi": 300,
            "figure.dpi": 100,
            "savefig.bbox": "tight",
        }
    )


def axis_label(spec: dict[str, Any], replication_unit: str, n_units: int | None) -> str:
    label = spec["label"]
    if spec["direction"] == "minimize":
        label += " (lower is better)"
    # Wrapped: a y label longer than its panel is tall runs into the panel above.
    lines = textwrap.wrap(label, width=AXIS_LABEL_CHARS) or [label]
    if n_units:
        lines.append(f"({n_units} {replication_unit}s)")
    return "\n".join(lines)


def draw_panel(
    ax,
    trials: list[dict[str, Any]],
    key: str,
    spec: dict[str, Any],
    accent: str,
    extra_values: list[float],
) -> None:
    """One dot per attempt: accepted filled in the accent, otherwise open in neutral."""
    spread_key = spec.get("spread")
    points = panel_points(trials, key, spread_key)
    if not points:
        fail(f"no attempt recorded a value for {key!r}")
    for trial, current, spread in points:
        kept = trial["status"] == "keep"
        crashed = trial["status"] == "crash"
        colour = accent if kept else NEUTRAL
        if spread:
            ax.plot(
                [trial["id"], trial["id"]],
                [current - spread, current + spread],
                color=colour,
                linewidth=1.0,
                alpha=0.75,
                zorder=2,
            )
        ax.plot(
            trial["id"],
            current,
            marker="x" if crashed else "o",
            markersize=KEEP_SIZE if kept else OTHER_SIZE,
            markerfacecolor=colour if kept else SURFACE,
            markeredgecolor=colour,
            markeredgewidth=1.3,
            linestyle="none",
            zorder=3,
        )
    low = min(current - spread for _, current, spread in points)
    high = max(current + spread for _, current, spread in points)
    low, high = min([low, *extra_values]), max([high, *extra_values])
    span = (high - low) or abs(high) or 1.0
    bottom, top = low - 0.12 * span, high + 0.18 * span
    limits = spec.get("limits")
    if limits:
        # A bounded metric never gets padding outside its domain.
        bottom, top = max(bottom, float(limits[0])), min(top, float(limits[1]))
    ax.set_ylim(bottom, top)


def draw_guide(ax, trials: list[dict[str, Any]], key: str) -> None:
    """Faint line joining the values; broken where an attempt has no value."""
    xs = [trial["id"] for trial in trials]
    ys = [value_of(trial, key) for trial in trials]
    ys = [math.nan if y is None else y for y in ys]
    ax.plot(xs, ys, color=NEUTRAL, linewidth=0.9, alpha=0.45, zorder=1)


def draw_objective(ax, trials, metadata, key, spec, accent) -> list[float]:
    """Incumbent step line and, when declared, the acceptance bar."""
    series = incumbent_series(trials, key, spec["direction"])
    if not series:
        return []
    xs = [trial_id for trial_id, _ in series]
    ys = [best for _, best in series]
    ax.step(xs, ys, where="post", color=accent, linewidth=1.5, alpha=0.95, zorder=1)
    delta = metadata.get("accept_delta")
    if delta is None:
        return ys
    signed = float(delta) if spec["direction"] == "maximize" else -float(delta)
    bar = [best + signed for best in ys]
    ax.step(
        xs,
        bar,
        where="post",
        color=TEXT_SECONDARY,
        linewidth=0.9,
        linestyle=(0, (4, 3)),
        alpha=0.8,
        zorder=1,
    )
    return ys + bar


def label_values(ax, trials, key, spec, which: str) -> None:
    places = decimals(trials, key, spec)
    for trial, current, spread in panel_points(trials, key, spec.get("spread")):
        kept = trial["status"] == "keep"
        if which == "keeps" and not kept:
            continue
        ax.annotate(
            f"{current:.{places}f}",
            (trial["id"], current + spread),
            textcoords="offset points",
            xytext=(0, 11),
            ha="center",
            fontsize=8.5,
            fontweight="bold" if kept else "normal",
            color=TEXT_PRIMARY,
        )


def footnote_text(metadata, trials, panels, accent_used, commits: bool) -> str:
    primary = metadata["primary_metric"]
    spec = metadata["metrics"][primary]
    crashes = [t for t in trials if t["status"] == "crash"]
    parts = [
        metadata["scope"].rstrip(". ") + ".",
        f"Unit of replication: {metadata['replication_unit']}.",
        "Filled accent: the run accepted the attempt and made it the incumbent;"
        " open: not accepted.",
    ]
    # The incumbent and the acceptance bar are drawn on the primary metric's
    # panel alone, so they are described only when that panel is shown.
    delta = metadata.get("accept_delta")
    if primary in panels:
        parts.append(f"Step line: best {spec['label']} among accepted attempts.")
        if delta is not None:
            sign = "+" if spec["direction"] == "maximize" else "-"
            parts.append(f"Dashed: acceptance bar (incumbent {sign}{float(delta):g}).")
    spreads = {
        metadata["metrics"][key]["spread"]
        for key in panels
        if metadata["metrics"][key].get("spread")
    }
    for spread_key in sorted(spreads):
        label = metadata["metrics"].get(spread_key, {}).get("label", spread_key)
        parts.append(f"Whisker: ±{label}.")
    if crashes:
        ids = ", ".join(f"{trial['id']:03d}" for trial in crashes)
        parts.append(f"Dotted rule: the attempt crashed ({ids}).")
        if any(value_of(trial, key) is not None for trial in crashes for key in panels):
            parts.append("×: a crashed attempt that still produced a measurement.")
    if commits:
        parts.append("Monospace text under each mark is the commit evaluated.")
    if len(panels) > 1:
        parts.append("Panels are different metrics and share no axis.")
    if metadata.get("note"):
        parts.append(metadata["note"].strip())
    if not accent_used:
        parts.append("No attempt was accepted.")
    return " ".join(parts)


def render(metadata, trials, panels, args) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    apply_style()
    accent = args.accent or metadata.get("accent") or ACCENT
    primary = metadata["primary_metric"]
    ids = [trial["id"] for trial in trials]
    crashes = [trial for trial in trials if trial["status"] == "crash"]
    accent_used = any(trial["status"] == "keep" for trial in trials)

    footnote = footnote_text(metadata, trials, panels, accent_used, args.commits)
    wrapped = textwrap.fill(footnote, width=int(FOOTNOTE_CHARS_PER_INCH * args.width))
    # Reserve inches for the furniture tight_layout cannot see -- the suptitle,
    # the legend, the footnote -- so the layout holds for any panel count and
    # any footnote length. Ticks, the commit rail and the x label sit inside the
    # rect, because the rail's room comes from the x label's pad.
    top_reserve = 0.78
    bottom_reserve = 0.12 + FOOTNOTE_LINE_INCHES * (wrapped.count("\n") + 1)
    ratios = [2.6] + [1.6] * (len(panels) - 1)
    height = sum(ratios) + top_reserve + bottom_reserve
    fig, axes = plt.subplots(
        len(panels),
        1,
        figsize=(args.width, height),
        sharex=True,
        height_ratios=ratios,
        squeeze=False,
    )
    axes = [row[0] for row in axes]

    n_units = metadata.get("units_per_trial")
    for ax, key in zip(axes, panels):
        spec = metadata["metrics"][key]
        extra: list[float] = []
        if key == primary:
            extra = draw_objective(ax, trials, metadata, key, spec, accent)
        else:
            draw_guide(ax, trials, key)
        draw_panel(ax, trials, key, spec, accent, extra)
        if args.labels != "none" and key == primary:
            label_values(ax, trials, key, spec, args.labels)
        ax.set_ylabel(axis_label(spec, metadata["replication_unit"], n_units))
        for trial in crashes:
            ax.axvline(
                trial["id"],
                color=RULE_GRAY,
                linewidth=1.0,
                linestyle=(0, (1, 3)),
                zorder=0,
            )

    bottom = axes[-1]
    step = max(1, math.ceil(len(ids) / 30))
    bottom.set_xticks(ids)
    bottom.set_xticklabels(
        [f"{i:03d}" if index % step == 0 else "" for index, i in enumerate(ids)],
        fontsize=7.5,
    )
    bottom.set_xlim(min(ids) - 0.75, max(ids) + 0.75)
    # The commit rail hangs below the tick labels, so the axis label moves down.
    bottom.set_xlabel("experiment id, in run order", labelpad=44 if args.commits else 4)
    if args.commits:
        for trial in trials:
            bottom.annotate(
                str(trial.get("commit", ""))[:7],
                (trial["id"], 0),
                xycoords=("data", "axes fraction"),
                textcoords="offset points",
                xytext=(0, -26),
                rotation=90,
                ha="center",
                va="top",
                fontsize=6.4,
                color=TEXT_SECONDARY,
                family="monospace",
            )

    # The key lists only marks the figure actually carries.
    key_marks = []
    if drawn(trials, panels, "keep"):
        key_marks.append(
            Line2D([], [], marker="o", linestyle="none", markersize=KEEP_SIZE,
                   color=accent, label="accepted — new incumbent")
        )
    if drawn(trials, panels, "discard"):
        key_marks.append(
            Line2D([], [], marker="o", linestyle="none", markersize=OTHER_SIZE,
                   markerfacecolor=SURFACE, markeredgecolor=NEUTRAL, markeredgewidth=1.3,
                   color=NEUTRAL, label="not accepted")
        )
    delta = metadata.get("accept_delta")
    if primary in panels:
        if accent_used:
            key_marks.append(
                Line2D([], [], color=accent, linewidth=1.5, label="incumbent")
            )
        if delta is not None:
            spec = metadata["metrics"][primary]
            sign = "+" if spec["direction"] == "maximize" else "-"
            key_marks.append(
                Line2D([], [], color=TEXT_SECONDARY, linewidth=0.9, linestyle=(0, (4, 3)),
                       label=f"acceptance bar (incumbent {sign}{float(delta):g})")
            )

    fig.align_ylabels(axes)
    fig.suptitle(metadata["title"], x=0.006, ha="left", y=1 - 0.12 / height)
    fig.legend(
        handles=key_marks,
        loc="upper left",
        bbox_to_anchor=(0.006, 1 - 0.52 / height),
        ncol=len(key_marks),
        fontsize=8,
        handletextpad=0.6,
        columnspacing=2.4,
    )
    fig.tight_layout(
        rect=(0, bottom_reserve / height, 1, 1 - top_reserve / height), h_pad=1.1
    )
    fig.text(
        0.006,
        0.012,
        wrapped,
        fontsize=7.6,
        color=TEXT_SECONDARY,
        ha="left",
        va="bottom",
        linespacing=1.55,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trials", help="path to <run>-trial-runs.jsonl")
    parser.add_argument("--out", help="output PNG path")
    parser.add_argument(
        "--panel",
        action="append",
        default=[],
        metavar="METRIC",
        help="metric key for one panel, top to bottom; repeatable "
        "(default: the run's primary metric)",
    )
    parser.add_argument("--commits", action="store_true",
                        help="draw the evaluated commit under each attempt")
    parser.add_argument("--labels", choices=("keeps", "all", "none"), default="keeps",
                        help="value labels on the primary panel (default: keeps)")
    parser.add_argument("--accent", help="hex colour for accepted attempts")
    parser.add_argument("--width", type=float, default=12.0, help="figure width in inches")
    parser.add_argument("--validate", action="store_true",
                        help="check the file against the schema and exit")
    args = parser.parse_args()

    metadata, trials = load(Path(args.trials))
    panels = args.panel or [metadata["primary_metric"]]
    for key in panels:
        if key not in metadata["metrics"]:
            fail(f"panel metric {key!r} is not declared in the metadata record")
    if args.validate:
        statuses = {status: 0 for status in STATUSES}
        for trial in trials:
            statuses[trial["status"]] += 1
        print(
            json.dumps(
                {
                    "run": metadata["run"],
                    "trials": len(trials),
                    **statuses,
                    "metrics": sorted(metadata["metrics"]),
                }
            )
        )
        return
    if not trials:
        fail(f"{args.trials} has no trial records to plot")
    if not args.out:
        fail("--out is required unless --validate is given")
    if Path(args.out).suffix != ".png":
        fail(f"--out must end in .png, got {args.out}")
    print(render(metadata, trials, panels, args))


if __name__ == "__main__":
    main()
