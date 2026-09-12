# The shared style module

Every plotting module in a project imports one `style.py`. It holds the entity
order, the entity colors and display names, the ink and surface constants, the
rcParams recipe, and the I/O helpers. Nothing else sets rcParams. Two figure
families that draw from the same module cannot drift apart. The recipe below is
matplotlib; the roles (fixed order, fixed colors, one setter, one saver) carry
to any library.

## Constants

```python
# Fixed evaluation order for every table and figure; never sorted alphabetically.
ENTITY_ORDER: list[str] = [...]

# Validated colorblind-safe hexes, assigned to ENTITY_ORDER in order. Never cycled:
# an unknown entity raises rather than silently reusing a color.
ENTITY_COLORS: dict[str, str] = dict(zip(ENTITY_ORDER, [...], strict=True))
DISPLAY_NAMES: dict[str, str] = {...}
METRIC_LABELS: dict[str, str] = {...}

# Ranked comparisons: every context row in one neutral, the focal row in the accent.
NEUTRAL = "#6b7280"
ACCENT = "#d9541e"

TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
RULE_GRAY = "#d9d8d3"
SURFACE = "#fcfcfb"
```

`color_for(entity)` and `display_name(entity)` raise `KeyError` with a message
saying where to add the entity. Silent fallback colors are how two entities end
up sharing a hue in a published figure.

## rcParams recipe

| Knob | Default | Why |
|---|---|---|
| `font.family` | `sans-serif` | Legible at 8 pt on screen and in print. |
| `font.size` | `9` | Base size; everything else is set relative to it. |
| `text.color` | `TEXT_PRIMARY` | Text is ink, never series color. |
| `axes.labelcolor` | `TEXT_SECONDARY` | Axis labels recede behind data. |
| `axes.labelsize` | `9` | |
| `xtick.color`, `ytick.color` | `TEXT_SECONDARY` | |
| `xtick.labelsize`, `ytick.labelsize` | `8` | Ticks are the least important text. |
| `xtick.major.size`, `ytick.major.size` | `3` | Short ticks read as marks on a rule, not furniture. |
| `xtick.major.width`, `ytick.major.width` | `0.8` | Matches the spine weight. |
| `axes.edgecolor` | `RULE_GRAY` | Spines are guides, not frames. |
| `axes.linewidth` | `0.8` | |
| `axes.spines.top`, `axes.spines.right` | `False` | Data-ink: they frame nothing. |
| `axes.grid` | `False` | Faint row rules or nothing. A grid competes with whiskers. |
| `axes.axisbelow` | `True` | Any rule drawn sits behind the data. |
| `axes.titlesize` | `10` | |
| `axes.titleweight` | `bold` | |
| `axes.titlelocation` | `left` | Reads as a heading, not a caption. |
| `axes.titlepad` | `6` | |
| `figure.titlesize` | `11` | Figure title one step above panel titles. |
| `figure.titleweight` | `bold` | |
| `figure.facecolor`, `axes.facecolor`, `savefig.facecolor` | `SURFACE` | Off-white surface; pure white glares next to gray rules. |
| `legend.frameon` | `False` | A legend box is a frame around a frame. |
| `legend.fontsize` | `8` | |
| `lines.linewidth` | `1.4` | Thin enough that bands and rules stay visible under it. |
| `savefig.dpi` | `300` | Print resolution. |
| `figure.dpi` | `100` | Screen preview only. |
| `savefig.bbox` | `tight` | Pulls footnotes hanging below the axes into the saved image. |

Per-figure overrides that are not rcParams: ranked dot plots hide the left spine
and set y tick length to 0; distributions keep a zero y baseline; curve figures
may bound the bottom spine to the tick range.

## Helpers

```python
def apply_style() -> None:
    """Apply the recipe above. Call once at the start of every plot entry point."""

FOOTNOTE_WIDTH = 120

def footnote(fig: Figure, text: str) -> None:
    """textwrap.fill(text, FOOTNOTE_WIDTH); 8 pt TEXT_SECONDARY, flush left at
    (0.01, -0.02), va='top'. Call after layout is final; savefig.bbox='tight'
    pulls it into the image."""

def save(fig: Figure, out_stem: Path) -> Path:
    """Write <out_stem>.png, creating parents. Return the path. PNG only."""
```

## Sizing

- Ranked or fixed-order dot plots: width 7.5 in (one panel) or 11 in (three
  panels); height `0.42 * n_rows + 1.6` in.
- Tables: width `1.75 * n_cols + 2.6` in, height `0.5 * n_rows + 1.6` in.
- Curves: 7 by 5 in. Small multiples: 4 in per panel side, at most 3 columns.

## Typography hierarchy

Figure title 11 pt bold, panel title 10 pt bold, axis label 9 pt, value labels
8 to 9 pt, ticks 8 pt, legend 8 pt, footnote 8 pt. Bold marks emphasis (the
focal row, the best cell); nothing else is bold.
