# Color and marks

## Color does one job per figure

**Job 1, identity.** Each entity owns one fixed color, assigned in the fixed
entity order from a validated colorblind-safe list. The color never changes
across figures, sessions, or filters. An entity absent from the list raises; it
is never given a generated or recycled hue. Use this job when several curves or
distributions must be told apart.

**Job 2, one bit.** Every context row in `NEUTRAL` gray; the focal row in
`ACCENT`. Use this job when the row label already names the entity, so a hue
per row would carry nothing. Ranked dot plots, fixed-order dot panels, and
tables use this job.

Never combine the two in one figure. Never use a rainbow or a cycled default
palette. The accent goes to a predeclared focal entity. In a single-metric
ranked plot with no focal entity it may mark the top row, but a rank-dependent
color is never carried across figures: if the winner changes between two
figures, a reader comparing them is misled.

## Conditions of the same entity

Fine-tuned vs zero-shot, single-stage vs two-stage, with vs without a
component: these are conditions of an entity, not new entities. Encode them
with a secondary channel that survives grayscale:

- dash pattern on curves,
- hatch on bars,
- hollow vs filled markers,
- marker shape (circle vs square) with a two-entry legend explaining it.

Never a second hue. Use the channel only when the condition is real and key it
once. A marker shape that varies without meaning is noise.

## Validation

Run a colorblind validator on any categorical palette before publishing it;
never judge separation by eye. The neutral-plus-accent pair intentionally fails
a "chroma floor" check because the neutral is gray; that is acceptable since
identity lives in the label, not the hue. Separation and contrast against the
surface must pass. Every essential distinction must survive a grayscale print,
and text and marks need enough contrast against the surface to read at the
final size.

## Marks

- Dot: `s=45` to `s=110` depending on density, filled with the row color.
- Whisker: the interval (house default ±1 std over the unit of replication),
  linewidth 1.2 to 1.5, same color as the dot, drawn under it.
- Row rule: `RULE_GRAY`, linewidth 0.5 to 1, constant length, under everything.
- Curve: linewidth 1.4, band `alpha` 0.12 to 0.15 in the curve color.
- Distribution fills: focal `alpha` 0.7 in entity color, context `alpha` 0.45 in
  `NEUTRAL`, drawn context first.
- Threshold or reference rule: dotted or dashed, `TEXT_SECONDARY`, linewidth 1.

## Intervals

Variability is shown, not implied. If repeats exist, the whisker or band is not
optional. Aggregate at the unit of replication first (one value per partition,
seed, or subject), then compute the interval over those. The house default is
mean ± 1 std, chosen because it shows spread without a distributional claim;
when the estimand needs a standard error, confidence interval, or bootstrap
interval, use it and name it. The footnote always names the statistic and the
unit: `mean over 25 partitions; whisker: ±1 std`. Paired comparisons are shown
as paired.

## Table shading

One sequential hue (a truncated `Blues`, roughly 0.05 to 0.50 of the map so text
stays legible). Normalize within a row, invert lower-is-better rows so darker is
always better, and say in the footnote that shading is not comparable across
rows. The exact values in each cell carry the cross-row reading. Two-pixel
surface-colored gaps between cells.
