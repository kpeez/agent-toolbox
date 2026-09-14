#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib>=3.8"]
# ///
"""Draw the standard single-objective progress plot for an autoresearch run.

    plot_trials.py RUN_DIR [--out PROGRESS.png] [--width INCHES]
    plot_trials.py RUN_DIR --validate

The run directory contains the append-only ``results.jsonl`` ledger and a
small ``trial-plot.json`` declaration. The declaration chooses the one metric
that the run is optimizing; this renderer owns the shared visual language.
Matplotlib is imported only when a figure is requested, so validation works in
a minimal Python environment.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

# Keep the standard plot's visual language here. Run-specific figures may add
# their own views, but should not need to fork this renderer.
GREEN = "#4fbd7a"
GREEN_DARK = "#31885a"
DISCARD = "#cfd3d1"
CRASH = "#a76b6b"
TEXT_PRIMARY = "#101313"
TEXT_SECONDARY = "#555c59"
RULE_GRAY = "#d9ddda"
SURFACE = "#fcfcfb"

STATUSES = ("keep", "discard", "crash")
DIRECTIONS = ("maximize", "minimize")
CONFIG_FIELDS = {"metric", "label", "direction", "title", "scope"}
REQUIRED_CONFIG_FIELDS = ("metric", "label", "direction", "title")
OLD_CONFIG_FIELDS = {"metrics", "primary_metric"}


def fail(message: str) -> None:
    raise SystemExit(f"plot_trials: {message}")


def require_nonempty_string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{where}: expected a non-empty string")
    return value.strip()


def require_number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f"{where}: expected a finite number, got {value!r}")
    result = float(value)
    if not math.isfinite(result):
        fail(f"{where}: expected a finite number, got {value!r}")
    return result


def load_config(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "trial-plot.json"
    if not path.is_file():
        fail(f"plot declaration not found: {path}")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"{path}: invalid JSON: {error}")
    except OSError as error:
        fail(f"cannot read {path}: {error}")
    if not isinstance(config, dict):
        fail(f"{path}: expected a JSON object")

    old = sorted(OLD_CONFIG_FIELDS & set(config))
    if old:
        fail(
            f"{path}: old plot schema {', '.join(repr(field) for field in old)} "
            "is unsupported; use metric, label, direction, and title"
        )
    unknown = sorted(set(config) - CONFIG_FIELDS)
    if unknown:
        fail(f"{path}: unsupported field(s): {', '.join(unknown)}")
    for field in REQUIRED_CONFIG_FIELDS:
        require_nonempty_string(config.get(field), f"{path}: {field!r}")
    if config["direction"] not in DIRECTIONS:
        fail(f"{path}: direction must be one of {', '.join(DIRECTIONS)}")
    if "scope" in config:
        require_nonempty_string(config["scope"], f"{path}: 'scope'")
    return config


def is_calibration_record(record: dict[str, Any]) -> bool:
    """Calibration belongs to its own ledger and must not make a best line."""
    phase = record.get("phase")
    if isinstance(phase, str) and phase.strip().lower() == "calibration":
        return True
    for key in ("description", "experiment"):
        value = record.get(key)
        if isinstance(value, str) and re.match(r"^\s*calibration\s*:", value, re.IGNORECASE):
            return True
    return False


def validate_record(record: Any, line: int, metric: str) -> dict[str, Any]:
    where = f"results.jsonl:{line}"
    if not isinstance(record, dict):
        fail(f"{where}: each line must be a JSON object")
    if is_calibration_record(record):
        fail(f"{where}: calibration records cannot be plotted with candidate attempts")

    identifier = record.get("id")
    if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier < 0:
        fail(f"{where}: id must be a non-negative integer")
    status = record.get("status")
    if status not in STATUSES:
        fail(f"{where}: status must be one of {', '.join(STATUSES)}")
    require_nonempty_string(record.get("description"), f"{where}: 'description'")
    metrics = record.get("metrics")
    if metrics is None:
        metrics = {}
    if not isinstance(metrics, dict):
        fail(f"{where}: 'metrics' must be an object")

    if metric not in metrics:
        if status != "crash":
            fail(f"{where}: non-crash record must contain metric {metric!r}")
    elif metrics[metric] is None:
        if status != "crash":
            fail(f"{where}: only a crash may record metric {metric!r} as null")
    else:
        require_number(metrics[metric], f"{where}: metrics[{metric!r}]")
    return record


def load_run(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not run_dir.is_dir():
        fail(f"run directory not found: {run_dir}")
    config = load_config(run_dir)
    path = run_dir / "results.jsonl"
    if not path.is_file():
        fail(f"results ledger not found: {path}")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        fail(f"cannot read {path}: {error}")

    records: list[dict[str, Any]] = []
    previous_id: int | None = None
    for line, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as error:
            fail(f"{path}:{line}: invalid JSON: {error}")
        record = validate_record(record, line, config["metric"])
        identifier = record["id"]
        if previous_id is not None and identifier <= previous_id:
            fail(f"{path}:{line}: ids must increase strictly ({identifier} follows {previous_id})")
        if record["status"] == "keep":
            value = metric_value(record, config["metric"])
            previous_keep = next(
                (metric_value(item, config["metric"]) for item in reversed(records) if item["status"] == "keep"),
                None,
            )
            if previous_keep is not None and value is not None:
                regressed = value < previous_keep if config["direction"] == "maximize" else value > previous_keep
                if regressed:
                    fail(f"{path}:{line}: keep metric regresses from {previous_keep:g} to {value:g}")
        previous_id = identifier
        records.append(record)
    return config, records


def metric_value(record: dict[str, Any], metric: str) -> float | None:
    value = (record.get("metrics") or {}).get(metric)
    return None if value is None else float(value)


def experiment_name(record: dict[str, Any]) -> str:
    """Return an explicit experiment name or preserve a legacy description."""
    identifier = record["id"]
    description = record["description"].strip()
    match = re.search(r"(?<![a-z0-9])exp(\d{3,})-[a-z0-9][a-z0-9-]*[a-z0-9]?(?![a-z0-9-])", description)
    if match and int(match.group(1)) == identifier:
        return match.group(0)
    return description


def apply_style() -> None:
    import matplotlib

    # The requested Karpathy-style progress view uses keyed green labels and
    # a faint lookup grid; its wider canvas needs slightly larger typography.
    matplotlib.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 10,
            "text.color": TEXT_PRIMARY,
            "axes.labelcolor": TEXT_SECONDARY,
            "axes.labelsize": 10,
            "xtick.color": TEXT_SECONDARY,
            "ytick.color": TEXT_SECONDARY,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "axes.edgecolor": TEXT_PRIMARY,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "figure.titlesize": 16,
            "figure.titleweight": "normal",
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "savefig.dpi": 300,
            "figure.dpi": 100,
            "savefig.bbox": "tight",
        }
    )


def running_best(keeps: list[tuple[dict[str, Any], float]], direction: str) -> list[tuple[int, float]]:
    better = max if direction == "maximize" else min
    best: float | None = None
    result: list[tuple[int, float]] = []
    for record, value in keeps:
        best = value if best is None else better(best, value)
        result.append((record["id"], best))
    return result


def figure_size(width: float, kept_names: list[str]) -> tuple[float, float]:
    """Give long runs room for labels while respecting --width as a floor."""
    total_chars = sum(len(name) for name in kept_names)
    automatic = max(8.0 + len(kept_names) * 0.12, 8.0 + total_chars / 48.0)
    width = max(width, min(automatic, 32.0))
    height = min(14.0, max(6.5, 6.2 + len(kept_names) * 0.025))
    return width, height


def label_polygon(annotation, renderer):
    """Rotated text rectangle; axis-aligned bounds overestimate diagonal labels."""
    from matplotlib.text import Text

    angle = annotation.get_rotation()
    annotation.set_rotation(0)
    box = Text.get_window_extent(annotation, renderer).padded(2)
    annotation.set_rotation(angle)
    x, y = annotation.get_transform().transform(annotation.get_position())
    cosine, sine = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return [(x + (a - x) * cosine - (b - y) * sine,
             y + (a - x) * sine + (b - y) * cosine)
            for a, b in ((box.x0, box.y0), (box.x1, box.y0),
                         (box.x1, box.y1), (box.x0, box.y1))]


def labels_overlap(first, second):
    """Separating-axis test for the two rotated text rectangles."""
    for polygon in (first, second):
        for a, b in zip(polygon, polygon[1:] + polygon[:1]):
            normal = (a[1] - b[1], b[0] - a[0])
            one = [x * normal[0] + y * normal[1] for x, y in first]
            two = [x * normal[0] + y * normal[1] for x, y in second]
            if max(one) < min(two) or max(two) < min(one):
                return False
    return True


def add_keep_labels(ax, keeps: list[tuple[dict[str, Any], float]], names: list[str]) -> None:
    """Keep every name legible; leaders retain its association when displaced."""
    canvas = ax.figure.canvas
    canvas.draw()
    renderer = canvas.get_renderer()
    boundary = ax.get_window_extent(renderer)
    placed = []
    rotation = 90 if len(keeps) > 25 else 32
    for (record, value), name in zip(keeps, names):
        annotation = ax.annotate(
            name, (record["id"], value), xytext=(4, 9),
            textcoords="offset points", rotation=rotation, rotation_mode="anchor",
            ha="left", va="bottom", fontsize=8.5, color=GREEN_DARK,
            arrowprops={"arrowstyle": "-", "color": RULE_GRAY, "lw": 0.65,
                        "shrinkA": 2, "shrinkB": 5},
            annotation_clip=False, zorder=5,
        )
        candidates = [(4, 9)]
        for distance in range(18, 300, 12):
            candidates.extend([(4, distance), (4, -distance)])
        for x_offset, y_offset in candidates:
            annotation.set_position((x_offset, y_offset))
            annotation.update_positions(renderer)
            polygon = label_polygon(annotation, renderer)
            if (all(boundary.x0 <= x <= boundary.x1 and boundary.y0 <= y <= boundary.y1
                    for x, y in polygon)
                    and not any(labels_overlap(polygon, previous) for previous in placed)):
                break
        else:
            # Keep the label rather than silently omitting it. The caller can
            # widen an unusually crowded figure and must inspect the PNG.
            print("warning: crowded kept labels; increase --width", file=sys.stderr)
        placed.append(polygon)
        if annotation.get_position() == (4, 9):
            annotation.arrow_patch.set_visible(False)


def save_figure(fig, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output)
    return output


def render(run_dir: Path, config: dict[str, Any], records: list[dict[str, Any]], output: Path, width: float) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    apply_style()
    metric = config["metric"]
    measured = [(record, metric_value(record, metric)) for record in records]
    measured = [(record, value) for record, value in measured if value is not None]
    keeps = [(record, value) for record, value in measured if record["status"] == "keep"]
    discards = [(record, value) for record, value in measured if record["status"] == "discard"]
    measured_crashes = [(record, value) for record, value in measured if record["status"] == "crash"]
    unmeasured_crashes = [record for record in records if record["status"] == "crash" and metric_value(record, metric) is None]
    names = [experiment_name(record) for record, _ in keeps]

    fig, ax = plt.subplots(figsize=figure_size(width, names))
    fig.subplots_adjust(left=0.09, right=0.98, top=0.83, bottom=0.13)
    ax.grid(color=RULE_GRAY, linewidth=0.8, alpha=0.55)
    if discards:
        ax.scatter([record["id"] for record, _ in discards], [value for _, value in discards], s=22, color=DISCARD, edgecolors="none", alpha=0.85, zorder=2)
    if measured_crashes:
        ax.scatter([record["id"] for record, _ in measured_crashes], [value for _, value in measured_crashes], marker="x", s=38, color=CRASH, linewidths=1.5, zorder=3)
    if keeps:
        ax.scatter([record["id"] for record, _ in keeps], [value for _, value in keeps], s=58, marker="o", color=GREEN, edgecolors=GREEN_DARK, linewidths=0.8, zorder=4)
        best = running_best(keeps, config["direction"])
        if records and records[-1]["id"] > best[-1][0]:
            best.append((records[-1]["id"], best[-1][1]))
        ax.step([identifier for identifier, _ in best], [value for _, value in best], where="post", color=GREEN, linewidth=2.2, alpha=0.95, zorder=1)

    ids = [record["id"] for record in records]
    if ids:
        lower, upper = min(ids) - 1, max(ids) + 1
        if lower == upper:
            lower, upper = lower - 1, upper + 1
        ax.set_xlim(lower, upper + (upper - lower) * 0.10)
        ax.set_xticks(ids if len(ids) <= 30 else thin_ticks(ids))
    else:
        ax.set_xlim(-0.5, 0.5)
        ax.set_xticks([])
    ax.set_xlabel("Experiment #")

    if measured:
        raw_values = [value for _, value in measured]
        low, high = min(raw_values), max(raw_values)
        span = high - low or max(abs(low) * 0.05, 1.0)
        ax.set_ylim(low - span * 0.15, high + span * (0.65 if len(keeps) > 25 else 0.35))
        direction_hint = "higher is better" if config["direction"] == "maximize" else "lower is better"
        ax.set_ylabel(f"{config['label']} ({direction_hint})")
    else:
        ax.set_yticks([])
        ax.set_ylabel(f"{config['label']} (no measurements)")
        ax.text(0.5, 0.5, "No measured objective values", transform=ax.transAxes, ha="center", va="center", color=TEXT_SECONDARY, fontsize=12)

    for record in unmeasured_crashes:
        # Axes-fraction rug: it marks a failed attempt without inventing y data.
        ax.plot([record["id"], record["id"]], [0.0, 0.035], transform=ax.get_xaxis_transform(), color=CRASH, linewidth=2.0, solid_capstyle="butt", zorder=5)

    handles = []
    if discards:
        handles.append(Line2D([], [], marker="o", linestyle="none", markersize=4.5, color=DISCARD, label="Discarded"))
    if keeps:
        handles.extend([Line2D([], [], marker="o", linestyle="none", markersize=7, color=GREEN, label="Kept"), Line2D([], [], color=GREEN, linewidth=2.2, label="Running best")])
    if measured_crashes:
        handles.append(Line2D([], [], marker="x", linestyle="none", markersize=6,
                              color=CRASH, label="Crash (measured)"))
    if unmeasured_crashes:
        handles.append(Line2D([], [], marker="|", linestyle="none", markersize=8,
                              color=CRASH, label="Crash (no metric)"))
    if handles:
        ax.legend(handles=handles, loc="lower right", bbox_to_anchor=(1, 1.02),
                  ncol=len(handles), frameon=False)

    fig.suptitle(config["title"], x=0.09, y=0.96, ha="left")
    noun = "experiment" if len(records) == 1 else "experiments"
    fig.text(0.09, 0.91, f"{len(records)} {noun}, {len(keeps)} kept", color=TEXT_SECONDARY, fontsize=10, ha="left")
    if config.get("scope"):
        fig.text(0.09, 0.02, config["scope"], color=TEXT_SECONDARY, fontsize=8.5, ha="left")
    # Add labels after all figure furniture exists. Collision bounds otherwise
    # change when the legend or title is laid out.
    if keeps:
        add_keep_labels(ax, keeps, names)
    result = save_figure(fig, output)
    plt.close(fig)
    return result


def thin_ticks(ids: list[int], maximum: int = 12) -> list[int]:
    if len(ids) <= maximum:
        return ids
    step = math.ceil(len(ids) / maximum)
    ticks = ids[::step]
    if ticks[-1] != ids[-1]:
        if len(ids) - 1 - ((len(ids) - 1) // step) * step < step / 2:
            ticks[-1] = ids[-1]
        else:
            ticks.append(ids[-1])
    return ticks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", help="autoresearch run directory")
    parser.add_argument("--out", help="output PNG path (default: RUN_DIR/progress.png)")
    parser.add_argument("--width", type=float, default=12.0, help="minimum figure width in inches (default: 12)")
    parser.add_argument("--validate", action="store_true", help="validate inputs and print a JSON summary without importing matplotlib")
    args = parser.parse_args()
    if not math.isfinite(args.width) or args.width <= 0:
        fail("--width must be a positive finite number")

    run_dir = Path(args.run_dir)
    config, records = load_run(run_dir)
    if args.validate:
        counts = {status: sum(record["status"] == status for record in records) for status in STATUSES}
        print(json.dumps({"metric": config["metric"], "experiments": len(records), **counts}))
        return

    output = Path(args.out) if args.out else run_dir / "progress.png"
    if output.suffix.lower() != ".png":
        fail(f"--out must end in .png, got {output}")
    print(render(run_dir, config, records, output, args.width))


if __name__ == "__main__":
    main()
