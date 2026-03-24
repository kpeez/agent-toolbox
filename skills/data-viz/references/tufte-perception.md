# Tufte And Perception

Use this file when you need the theory behind plotting choices.

## Tufte's core rules

- Above all else, show the data.
- Maximize data-ink ratio.
- Erase non-data ink.
- Erase redundant data ink.
- Revise and edit.
- Avoid chartjunk and graphical distortion.
- Use small multiples for structured comparison.
- Integrate words, numbers, and graphics.

## What those rules mean in practice

- Remove heavy borders, shadows, gradients, textures, and 3D effects.
- Keep only the scaffolding that improves reading: light grids, direct labels, reference lines,
  uncertainty intervals, source notes.
- Favor high-information layouts over decorative ones.
- When a plot becomes overloaded, split it into small multiples rather than piling on encodings.

## Perceptual ranking for quantitative comparison

Default order:

1. Position on a common scale
2. Length
3. Angle and slope
4. Area and volume
5. Color hue for exact numeric comparison

Practical consequences:

- Prefer dots and bars over pies and bubbles for precise comparisons.
- Use aligned scales whenever comparison across groups matters.
- Do not expect readers to decode many numeric differences from area or hue alone.

## Honesty rules

- Bars on linear scales start at 0.
- Bars on log scales start at 1 because they show ratios.
- If value is encoded by area, scale the area, not the radius.
- Keep graphical effect proportional to numeric effect.
- Avoid design choices that manufacture drama from small differences.
