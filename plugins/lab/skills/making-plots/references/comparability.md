# Comparability

A figure that puts incomparable numbers on one axis is wrong even when every
number on it is correct. Before combining rows on an axis, every row must agree
on: the metric and its definition, the population it was measured on, the
denominator or chance rate, the scoring implementation, and the protocol.

## Never share an axis across

- **Populations with different chance rates or denominators.** 1-of-8 and
  1-of-20 identification are different tasks. Separate figures; shared tick
  ranges are allowed.
- **Scoring implementations.** Filter to one scorer before drawing. Refuse
  inputs that cannot say how they were scored.
- **Oracle vs end-to-end inputs.** A result computed with ground truth handed
  to one stage (for example, pose scored on ground-truth boxes) excludes the
  error of the stage it skipped. It is a ceiling, not a competitor. It reaches
  no ranked figure; it may appear in a table labeled as a ceiling.
- **Selection data vs held-out data.** Numbers from the data a model was
  selected on are optimistic. Say so in the results note; keep them in their
  own figure.

## Filters, not footnotes

When a comparison is invalid, remove the rows in the loader or adapter so the
mixed axis is unreachable. A footnote is documentation for a valid figure, not a
safeguard for an invalid one. Raise on duplicate `(entity, condition,
population)` keys, on populations whose entries disagree about sample counts,
and on unknown entities.

## Carry the handicap

When entities bring different upstream quality into the compared metric (a
two-stage system depends on its first stage's recall), show that upstream
number beside each row so the reader sees the handicap rather than infers it.

## Sparse strata

Do not plot a stratum with too few observations to support a reading (a
size-stratified metric computed on a handful of instances). Leave it out and
say why.

## Selection of what to plot

Plot every metric worth publishing, but aggregate first into one summary file
derived from an explicit run list, then plot from that file. Choose a headline
of two to four metrics that answer the scientific question; the rest go in the
table. Drop any figure whose readable content is already in the table.
