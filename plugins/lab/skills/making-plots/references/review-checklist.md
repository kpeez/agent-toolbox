# Review checklist

Run before calling a figure done.

## Question
- One sentence says what the figure shows and one names the unit of
  replication. The title names what is compared and on what data.
- Nothing on the figure is already shown more directly elsewhere.

## Honesty
- No bar, stem, or filled area starts above zero.
- Dots, whiskers, and curves are on axes scaled to their data; below-reference
  values are included when they occur.
- No population, scorer, oracle-input, or protocol mix on one axis. Filters,
  not footnotes.
- Every axis label has a unit or definition; transformations are named.
- Chance or reference is computed from the data and drawn only if in range.
- Variability is shown, aggregated at the unit of replication, and the
  statistic is named in the footnote.
- Inputs were validated: finite, unique keys, sorted x, positive on log axes.

## Encoding
- Color does one job: fixed entity colors, or neutral plus one accent on a
  predeclared focal entity.
- Shape, dash, hatch, fill appear only for a real condition, each keyed once,
  and every distinction survives grayscale.
- Text is ink colored. Best is marked by weight, outline, or underline, on
  unrounded values, with ties marked.
- Focal entity leads (top row, leftmost column), its baseline adjacent, then
  the fixed order; ranked by value only when rank is the message.
- Sibling figures share entity order and one axis range per metric.

## Furniture
- No grid by default, no top or right spine, no legend frame, no library name.
- Legend present only where direct labels could not do the job.
- Footnote wrapped at ~120 characters; states scope, marks, conventions, and
  off-scale references.
- Fonts: title 11/10 bold, labels 9, ticks and notes 8.

## Output
- One PNG at 300 dpi via `save()`, under the population folder. No PDF.
- Rendered and inspected at display size: no collisions, no clipped marks, no
  empty half-panel.
- Checks and tests pass; tests name invariants.
