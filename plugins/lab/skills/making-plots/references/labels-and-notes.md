# Labels, legends, titles, notes

## Titles

One left-aligned bold title per figure that names what is compared and on what
data, for example `headline metrics — test pool`. Panel titles are the metric's
display label. Titles do not restate the footnote, the method, or the library.

## Direct labels first

Label curves at the point where they separate, not necessarily the right edge.
When endpoints collide, spread the label positions apart by a minimum gap and
connect each label to its curve with a thin leader in the curve color. When
labels would cover data even after spreading, fall back to a frameless legend.
Label dots with their value, 8 to 9 pt, primary ink, offset 6 to 10 pt after
the whisker end, unclipped, bold only on the focal row and still in ink, not in
the accent.

A legend remains only when direct labels cannot identify the marks or when a
shape or dash needs a key. Then: frameless, 6.5 to 8 pt, lower right above the
x axis, stacked in one column. Never a legend that repeats what labels already
say.

## Reading order

Importance runs top to bottom and left to right. Put the take-home message
where the eye lands first: the focal entity in the top row or leftmost column,
its own baseline adjacent, everything else after in the fixed order. Sibling
figures list entities in the identical order.

## Marking the best

- Overall best: bold text plus an accent outline (table cell) or bold label and
  accent mark (dot row).
- Best baseline: underline the value. Matplotlib has no underline; draw a thin
  `Line2D` in figure coordinates from the text's rendered extent after
  `tight_layout`.
- Compare unrounded values. Honor direction; lower-is-better metrics get the
  minimum and a `(lower is better)` suffix on their header. Mark ties as ties
  rather than picking one.

## Footnotes

One footnote per figure, 8 pt, `TEXT_SECONDARY`, flush left below the axes,
wrapped with `textwrap.fill(text, width=120)`. One unbroken line is wider than
the axes, and `savefig.bbox="tight"` then grows the canvas to fit it, leaving
the panels adrift in empty surface. It carries what a reader lifting the figure
into a slide needs:

1. The data scope and unit of replication: `20 enrolled / 5 distractor
   subjects`, `25 partitions`, or `5 seeds`, whichever applies.
2. What the marks mean: `Dot: mean; whisker: ±1 std. Band: ±1 std. Dashed: fine-tuned.`
3. Conventions: `Underlined: best zero-shot backbone. Outlined: best model.`
4. Anything off-scale or transformed: `Chance (1/20 = 0.050) falls below the
   plotted range.`

Do not use the footnote to excuse an invalid comparison. Filter the data
instead. Provenance (run ids, commit, data version) lives in the summary file
and the results note, not in the figure.

## Text color

Values, axis labels, ticks, legend text, and notes are primary or secondary
ink; the mark beside the text carries identity. A direct label that replaces a
legend on a curve may take the curve's color, since it is the key. Nothing else
is series colored.

## Display names

Display names live in one dictionary in the style module. Compose compound
labels in code (`"<detector> + <pose>"`) rather than storing variants. Never
expose private identifiers (real subject or animal ids) in a figure; use the
documented display labels.
