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

The ranking in SKILL.md (position on a common scale > length > angle/slope >
area/volume > hue) is Cleveland & McGill's result on graphical perception:
readers decode position on a common scale with the lowest error and area/hue with
the highest. That is the *why* behind the body's rules — prefer dots and bars over
pies and bubbles, aligned scales over stacked ones, and never lean on area or hue
alone for exact numeric differences: each step down the ranking widens the
reader's decoding error.

## Honesty rules

- Bars on linear scales start at 0.
- Bars on log scales start at 1 because they show ratios.
- If value is encoded by area, scale the area, not the radius.
- Keep graphical effect proportional to numeric effect.
- Avoid design choices that manufacture drama from small differences.
