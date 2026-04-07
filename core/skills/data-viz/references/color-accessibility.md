# Color And Accessibility

Use color to encode meaning, not decoration.

## Choose the right palette type

- Categorical palette: unordered groups
- Sequential palette: ordered low-to-high values
- Diverging palette: ordered values around a meaningful midpoint such as 0 or target

## Strong defaults

- Use one accent color for emphasis and mute the rest.
- Avoid rainbow and other non-monotonic scales for numeric data.
- Keep the same semantic category in the same color across related plots.
- Pair color with shape, line type, marker form, or direct labels when categories matter.

## Accessibility rules

- Do not rely on color alone to convey meaning.
- Ensure essential graphical objects have enough contrast against the background.
- Aim for at least 3:1 contrast for critical lines, points, borders, and slices.
- Test the plot in grayscale.
- Avoid tiny marks that differ only by hue.
- Use darker shades for text and outlines than for filled areas of the same hue.

## Review questions

- Would the plot still work for a color-vision-deficient reader?
- Would it still work on a projector or washed-out printout?
- Are highlighted marks distinguishable by lightness as well as hue?
- Is any legend entry doing work that a direct label could do better?
