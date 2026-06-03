# Chart Selection

Pick the chart from the comparison the user needs.

## Default choices

- Compare values across categories: sorted bar chart or dot plot
- Show change over time or another ordered axis: line chart
- Show a relationship between two quantitative variables: scatter plot
- Show one distribution: histogram, density plot, or ECDF
- Compare many distributions: boxplot, violin plot, ridgeline, or small multiples
- Show part-to-whole: stacked bar or 100% stacked bar; use pie/donut only for very simple cases
- Show many repeated comparisons: small multiples
- Show spatial data: map only when geography matters more than exact numeric comparison
- Show uncertainty: intervals, bands, distributions, or scenario/HOP-style views

## Fast rules

- Use lines only for ordered x-axes.
- Use bars only when the encoded length has a meaningful zero on a linear scale.
- Prefer dots over bars when bars add ink but not clarity.
- Prefer scatter over connected lines for unordered categories.
- Prefer small multiples over one overloaded plot.
- Prefer direct labels over separate legends when feasible.

## Use with caution

- Pie and donut charts:
  Use only when there are very few parts, the message is broad part-to-whole, and precise
  comparison is not important.
- Heatmaps:
  Good for matrices and dense patterns, weaker for exact value lookup.
- Dual-axis charts:
  Avoid by default; they often imply false relationships and make scales hard to read.
- Bubble charts:
  Use only when rough ranking is enough; area judgments are weak.
- Radar/spider charts:
  Avoid unless there is a strong domain convention and no better alternative.

## Helpful conversions

- Crowded multi-line chart -> highlight a few series or facet into small multiples
- Long category names on vertical bars -> switch to horizontal bars or dots
- Stacked bars used for subgroup comparison -> grouped bars, dots, or small multiples
- Pie chart used for precise comparison -> bar chart
- Raw-count choropleth -> normalized rate map or proportional-symbol map
