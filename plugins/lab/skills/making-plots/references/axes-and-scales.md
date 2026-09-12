# Axes and scales

## When zero is mandatory

A mark that encodes magnitude as a length or area from a baseline must start at
zero: bars, stems, stacked segments, filled histograms and densities.
Truncating the baseline stretches small differences into large ones, and the
reader's eye does not read the tick label that would correct it. A filled band
that shows an interval around a curve is not such a mark; it encodes width, not
height from zero.

A stem from the axis edge to a dot is a bar. If the axis starts above zero,
replace the stem with a constant-length row rule that spans the full axis.

## When zero is wrong

Dots, whiskers, and curves encode value by position, not length. For these,
scale the axis to the data. A rate axis pinned to `[0, 1]` when every value sits
between 0.55 and 0.62 hides the comparison the figure exists to make. For a
bounded score with a chance level, start the axis just under chance when no
value falls below it; when values do fall below chance, include them, since a
below-chance score is a finding (inversion, systematic failure), not noise.

## Deriving limits

```python
LIMIT_SNAP = 0.05
TICK_STEPS = (0.05, 0.1, 0.2, 0.25, 0.5)

def axis_limits(values, domain=(None, None), max_ticks=6) -> tuple[lo, hi, step]:
    # values: every mark position to show, including whisker ends and any
    # reference value you intend to draw. All finite; raise otherwise.
    pad = 0.05 * max(max(values) - min(values), 0.02)
    lo = floor((min(values) - pad) / LIMIT_SNAP) * LIMIT_SNAP
    hi = ceil((max(values) + pad) / LIMIT_SNAP) * LIMIT_SNAP
    lo, hi = clamp to domain where a bound is given (rates: (0.0, 1.0))
    step = first s in TICK_STEPS with (hi - lo) / s <= max_ticks - 1
```

The snap and step tables above suit rates in `[0, 1]`; scale them to the
metric (latency in ms, AP in percent). Clamp only when the domain is known.
Place ticks on multiples of the step with `MultipleLocator(step)`, never at
`lo + k * step`: limits of 0.35 to 0.95 with a 0.2 step show 0.4, 0.6, 0.8, not
0.35, 0.55, 0.75. Ticks read as numbers a person would say. Never more than six
or seven major ticks on a value axis; integer locators on rank and count axes.

## Room for marks and labels

Reserve a gutter beyond the last tick for value labels, and draw dots and
whiskers with `clip_on=False` so a mark at 0.99 is not sliced by the axis edge.

## Shared limits across sibling figures

Figures for different populations never share an axis, but siblings share one
range per metric. Compute each metric's limits once over every sibling and pass
the same limits to each figure, so a reader can flip between them and read the
shift directly. The ticks show the range; the footnote does not need to say the
axis is scaled.

## Reference rules

Draw chance, a baseline, or an operating point as a dotted rule in
`TEXT_SECONDARY`, labeled once in 7 to 8 pt. Draw it only when it lies inside
the plotted range. When it falls outside, name it and its value in the
footnote. Compute it from the data and the metric definition, never from a
constant typed into the plot.

## Log axes

Use a log axis when the metric is defined on one and spans decades (a false
positive rate from 1e-3 to 1). Name the scale in the axis label. Reject or
transform nonpositive values before drawing and report how many. Mark decades
as major ticks; minor ticks stay faint. Bars on a log axis have no baseline;
use points.

## Units and transformations

Every axis label carries the unit or the metric definition (`Box AP (%)`,
`latency (ms)`, `FNIR at FPIR 0.1`). Percent and proportion never share an
axis. Any normalization, log, or smoothing is named on the label or in the
footnote.

## Input validation

Before drawing: values finite, keys unique per (entity, condition,
population), x sorted for curves, positive for log axes, denominators nonzero.
Fail loudly with the offending keys and counts. A silently dropped row is a
wrong figure that looks right.
