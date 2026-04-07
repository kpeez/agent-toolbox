---
name: data-viz
description: Research-backed guidance for designing, reviewing, and refining data visualizations, plots, charts, dashboards, and scientific figures. Use when Codex needs to choose a chart type, improve an existing plot, write plotting code in Python/R/JavaScript, or critique a figure for clarity, statistical honesty, accessibility, labeling, annotation, and color use.
---

# Data Viz

## Overview

Use this skill before choosing a chart, while writing plotting code, and again after the first
draft as a review pass. The goal is to produce plots that are honest, comparison-friendly,
self-contained, and accessible. When you need more detail, load these files on demand:

- `references/chart-selection.md`
- `references/tufte-perception.md`
- `references/color-accessibility.md`
- `references/review-checklist.md`

## Default Workflow

### 1. Frame the task

Before choosing a chart, identify:

- the exact question the plot should answer
- the audience and how much statistical background they likely have
- the variables, units, and whether the x-axis is ordered
- whether uncertainty, missingness, or sample size materially affect interpretation

If the plotting request is vague, state the inferred analytical task in one sentence before writing
code.

### 2. Pick the chart from the comparison

Use the simplest chart that makes the intended comparison easy.

- category comparison -> sorted bars or dots
- trend over ordered x-axis/time -> line
- relationship -> scatter
- distribution -> histogram, density, ECDF, boxplot, violin
- part-to-whole -> stacked bars before pie/donut in most cases
- many repeated comparisons -> small multiples

Load `references/chart-selection.md` if the right chart family is not obvious.

### 3. Prefer strong encodings

Default ranking for quantitative precision:

1. Position on a common scale
2. Length
3. Angle and slope
4. Area and volume
5. Color hue for exact reading

Implications:

- prefer dots and bars over pies and bubbles when precision matters
- prefer aligned comparisons over stacked ones
- avoid using hue as the only way to convey exact numeric differences

Load `references/tufte-perception.md` when you need the rationale.

### 4. Apply the plotting rules

- Bars on linear scales start at `0`.
- Bars on log scales start at `1`.
- Use lines only for ordered axes.
- Avoid dual axes by default.
- Avoid 3D effects, shadows, gradients, and decorative textures.
- Prefer direct labels over legends when feasible.
- Sort categories unless a domain order matters more.
- Split crowded figures into small multiples instead of piling on encodings.
- Keep titles, axis labels, units, and notes explicit.

### 5. Make the figure self-contained

The plot should stand on its own.

- write a title or caption that states the point, not just the subject
- label axes and units
- add source, timeframe, and transformation notes when needed
- annotate thresholds, interventions, outliers, and notable regime changes when they matter

### 6. Run the accessibility and honesty pass

- do not use color as the only cue
- ensure critical marks have enough contrast against the background
- test whether the plot would still work in grayscale
- use one accent color for emphasis and keep context muted
- use uncertainty intervals, bands, or distributional views when uncertainty changes interpretation

Load `references/color-accessibility.md` for palette and contrast guidance.

### 7. Review the final result

Load `references/review-checklist.md` and check the plot against it before calling the work done.

## Default Stance

- Tufte minimalism means remove friction, not useful context.
- A clean figure is not enough; the geometry must still be statistically honest.
- If a plot is hard to explain in one paragraph, it is usually the wrong plot.
- When in doubt, choose comparison clarity over novelty.

## Output Expectations

When creating or revising a plot:

- briefly state why the chosen chart fits the task
- implement the plot using sane defaults instead of library defaults where those conflict with this
  skill
- mention any notable tradeoffs such as truncated axes, log scaling, normalization, uncertainty
  treatment, or accessibility constraints

## References

- `references/chart-selection.md`
- `references/tufte-perception.md`
- `references/color-accessibility.md`
- `references/review-checklist.md`
