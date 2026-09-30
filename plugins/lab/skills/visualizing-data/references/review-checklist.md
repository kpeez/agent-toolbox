# Plot Review Checklist

Use this as the final pass after drafting a plot or plotting script.

## Message

- What exact question does the plot answer?
- Does the title or caption state the main takeaway?
- Is the figure understandable without the surrounding paragraph?

## Encoding

- Is the chart type appropriate for the task and data semantics?
- Am I using a strong encoding for the comparison that matters?
- Are any lines connecting unordered categories?
- Are any areas or bubbles being used where bars or dots would be clearer?

## Honesty

- Are baselines, scales, and transformations honest?
- If marks encode magnitude as length or area from a baseline (bars, stems,
  filled histograms or densities), do they start at a meaningful zero? Use dots
  when a truncated range is needed; interval bands are not magnitude marks.
- If a log scale is used, is it clearly labeled and justified?
- Is any visual effect exaggerated relative to the underlying numbers?

## Friction

- Can I remove borders, heavy grids, gradients, or 3D effects?
- Can I replace the legend with direct labels?
- Are units, timeframes, and sources present where needed?
- Are long labels rotated when a better layout would avoid that?

## Comparison

- Should the categories be sorted?
- Is category order meaningful for this question? When comparing related
  panels, is the order matched so rows can be followed across them?
- Would small multiples beat one crowded panel?
- Are scales, colors, and ordering consistent across panels?

## Accessibility

- Is color the only cue anywhere?
- Do critical graphical objects contrast enough with the background?
- Does the plot still work in grayscale?
- Are fonts, line widths, and markers readable at the intended display size?

## Completeness

- Should uncertainty be shown?
- Is missingness visible or explained?
- Are smoothing, aggregation, or normalization choices documented?
- Has the rendered figure been inspected at its intended display size for
  collisions, clipped marks or labels, and wasted space?
