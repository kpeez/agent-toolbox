---
name: making-plots
description: House rules for making publication- or report-quality scientific result figures with matplotlib or any plotting library. Use whenever the user asks to plot, chart, graph, visualize, compare, or tabulate results, metrics, benchmarks, training curves, distributions, or evaluation outputs, and whenever you are about to write or edit plotting code, choose axis limits, colors, markers, legends, or figure layout, even if the user does not say "plot". For a throwaway exploratory plot apply only the honesty rules. Encodes Tufte-style minimalism, data-scaled axes, honest baselines, one-job color, direct labels, and a shared style module.
---

# Making plots

A result figure is read by a reviewer who did not run the experiment. These
defaults exist so the figure tells that reader the true size of a difference
with the least ink. Each rule names the misreading it prevents; depart from one
only when you can name a better reason and say so in the code comment.

Vocabulary: an **entity** is the thing being compared (a model, a method, a
treatment). A **condition** is a variant of an entity (fine-tuned vs zero-shot,
with vs without a component). The **focal** entity is the one the figure is
about, if there is one. A **baseline** is what it is compared against. The
**unit of replication** is what the uncertainty is computed over (partitions,
seeds, subjects, runs). Examples in this skill come from model benchmarks; the
rules do not depend on them.

## Procedure

1. Name the question the figure answers in one sentence and the unit of
   replication in another. If the question needs two sentences, it is two
   figures.
2. Pick the figure type from the catalog below. A table is a valid answer.
3. Load `references/style-module.md` and draw through the project's shared
   style module. Never set rcParams inside a plot function.
4. Validate inputs (finite, no duplicate keys, positive on log axes), then
   draw. Scale axes to the data unless the mark encodes magnitude as length or
   area from a baseline (`references/axes-and-scales.md`).
5. Render the PNG and look at it. Fix collisions, clipped marks, and empty
   space before calling the work done.
6. Run `references/review-checklist.md`.

## Universal rules

- Do not start an axis at zero by default. Zero is mandatory only when a mark
  encodes magnitude as a length or area from a baseline: bars, stems, stacked
  segments, filled histograms and densities. A band that shows an interval is
  not such a mark.
- Never truncate a bar. If the interesting range starts above zero, draw dots.
- Never put incomparable numbers on one axis: different populations, chance
  rates, denominators, scorers, or protocols. Filter before drawing so the
  mixed axis is unreachable. A footnote documents; a filter guarantees.
- Every axis label carries the unit or the metric definition, and names any
  transformation (log, percent, normalized). Lower-is-better metrics say so.
- Color does one job per figure. Either it identifies entities with fixed
  colors that never change across figures, or it carries one bit (focal vs
  context) as neutral gray plus one accent. Never both. Never a rainbow.
- The accent belongs to a predeclared focal entity. In a single-metric ranked
  plot with no focal entity it may mark the top row; never carry a
  rank-dependent color across figures, because the winner can change.
- Shape, hatch, dash, and fill distinguish a condition of the same entity. Use
  them only when they mean something and key them once. A marker shape that
  varies for decoration is a defect. Every essential distinction survives
  grayscale.
- Prefer direct labels to a legend box. Keep a legend only when direct labels
  would collide or when a shape or dash needs a key.
- Values, ticks, labels, and notes are ink colored (primary or secondary),
  never series colored. The one exception is a direct label that replaces a
  legend on a curve; it may take its curve's color because it is the key.
- No grid by default. No top or right spine. Thin rules, small markers, 8 pt
  ticks. A sparse, faint grid is allowed only when it measurably helps lookup
  in a dense curve plot.
- Every figure stands alone: a left-aligned bold title naming what is compared
  and on what data, and a flush-left 8 pt footnote stating the data scope and
  unit of replication (for example `20 enrolled / 5 distractor subjects, 25
  partitions`), what the mark and interval mean, and any convention such as
  underline or outline. Wrap the footnote at about 120 characters.
- One PNG at 300 dpi per figure through the shared `save()` helper. No PDF
  unless the venue or the user asks. Figures specific to one population or
  condition go in a sub-folder per population.
- Show variability when repeats exist. House default: dot at the mean, whisker
  of ±1 std over the unit of replication; light band on a curve. Aggregate at
  that unit before computing the interval, and name the statistic in the
  footnote. Use a different interval when the estimand calls for it and name
  that instead.
- Mark "best" with weight and outline, not color: bold plus accent outline for
  the overall best, underline for the best baseline. Compare unrounded values,
  honor metric direction, and mark ties as ties.
- Importance runs top to bottom and left to right. The first thing the viewer
  sees is the take-home message: the focal entity is the top row of a dot plot
  and the leftmost column of a table, its own baseline sits directly adjacent
  so the gain reads off neighboring rows or cells, and the remaining entities
  follow in the fixed catalog order. Never let the winner land at the bottom
  because a fixed order happened to end there.
- Sibling figures are the same figure for different populations, or a dot plot
  and the table that carries its full record. Siblings list entities in the
  identical order and share one axis range per metric, computed once over all
  of them, so a reader can flip between them.

## Figure catalog

### Ranked dot plot (one metric, several entities)

Use when rank on a single metric is the message. Rows sorted by value, best on
top. One neutral color for every row's dot and whisker; the top row's dot and
whisker alone in the accent, with its row label and value in bold ink. Value
printed right of the dot at 9 pt. Constant-length faint row rules guide the
eye; they encode nothing. Left spine hidden, y ticks length 0. Marker shape
only for a real categorical split, with a two-entry frameless legend in the
lower right. Axis limits from the data, snapped to a clean step. Height grows
with row count (`0.42 * n + 1.6` in).

### Fixed-order dot panels (several metrics, several entities)

Use for a headline of two to four metrics. Rows keep one order across every
panel, so an entity never jumps rows: the focal entity on top, its own baseline
directly beneath it, then the remaining entities in the fixed catalog order.
Neutral rows, focal row in accent. Dot is the mean, whisker the interval, value
label anchored after the whisker end, unclipped. Each metric's x range is
computed once over every sibling figure and reused. A chance or reference
value is drawn as a dotted rule only when it falls inside the range; otherwise
the footnote says where it is. Underline the best baseline value per panel.

### Benchmark table (many metrics, many entities)

Use when several metrics must be shown and no single row order is honest for
all of them. Metrics as rows, entities as columns, focal entity in the
leftmost column with its own baseline beside it, remaining entities in fixed
order. Cell text `mean ± std` in primary ink. Shading is one sequential hue
normalized within the row, inverted for lower-is-better, so darker is always
better; the footnote says shading is not comparable across rows. Best cell per
row bold with an accent outline; best baseline per row underlined. This is the
complete record; the dot plot is the headline.

### Curves (for example ROC, DET, CMC, calibration, training trajectories)

Fixed entity color per curve, dash for a second condition of the same entity.
x sorted; the aggregation (mean over units) and any smoothing or resampling
stated in the footnote. Mean line with a light interval band. Direct labels at
the point where curves separate, spread apart with thin leaders when endpoints
collide; fall back to a frameless legend when labels would cover data.
Reference rules (operating points, a baseline value) dotted in secondary ink
and labeled once. Log axis when the metric is defined on one and spans decades,
with the scale named on the axis label and nonpositive values rejected before
drawing. y scaled to the data. Drop a curve figure whose only readable points
are already in the table.

### Distributions (histograms, densities)

One small-multiple panel per entity, at most three columns, shared x and y.
Focal fill in the entity color, context fill in neutral gray, one threshold
rule per panel. Density is an area, so y keeps its zero baseline. Bin edges
are fixed constants spanning the metric's domain. Clip only floating-point
round-off that lands a hair outside a bounded domain (a cosine of 1.0000001);
never clip real values into edge bins. If data fall outside the edges, widen
the edges or report the excluded count.

### Bars

Allowed only when the value is a magnitude from zero that the reader must
compare as length: latency stacks, counts. Baseline at zero, always. Stacked
segments only for an additive decomposition, in a fixed segment order, with a
surface-colored gap between fills. Value labels inside segments when they fit,
total at the bar end. Negative values get their own figure type. If the axis
wants to start above zero, the figure wants dots.

### Scatter and frontier

x and y each scaled to their data with room for point labels. Dominated points
smaller and grayer than the nondominated set. Connect the frontier with a
dashed neutral guide only when both axes are continuous and the connection
means something; otherwise leave the set unconnected. Label points directly;
never a legend of point names.

## Ordering

Importance first, then the fixed catalog order. The focal entity leads (top
row, leftmost column), its own baseline is adjacent, and every other entity
follows in the fixed, documented order. Sort by value only when the figure's
single message is rank on one metric. Never sort alphabetically. Never reorder
because a filter removed rows. Siblings use the identical order. Chance and
reference values come from the data and the metric definition (`1 / n_classes`
for a closed-set rank-1, `0.5` for AUROC), never a constant typed into the
plot.

## What not to plot

- Oracle-input results next to end-to-end results (for example, pose scored on
  ground-truth boxes beside pose scored on detected boxes). The oracle number
  is a ceiling; it may appear in a table labeled as one.
- Strata with too few observations to support the reading.
- The same encoding twice at two widths. If a bar chart repeats the dot panels
  plus the table, delete the bar chart.
- Rows from mixed scorers or protocols with a caveat. Filter them or refuse.

## References

- `references/style-module.md`: the shared matplotlib recipe and helpers: each
  rcParams knob with its default and reason, palette constants, `save()`,
  `footnote()`, sizing, typography.
- `references/axes-and-scales.md`: when zero is mandatory, data-scaled limits,
  tick placement, reference rules, log axes, input validation.
- `references/color-and-marks.md`: the two color jobs, fixed entity colors,
  neutral plus accent, condition channels, validation, marks and intervals.
- `references/labels-and-notes.md`: titles, direct labels, legends, footnotes,
  marking the best, reading order, font sizes.
- `references/comparability.md`: what may not share an axis and how to encode
  comparability as a filter.
- `references/code-organization.md`: style module, primitives vs adapters,
  one summary input, provenance, tests, output layout.
- `references/review-checklist.md`: the final pass.
