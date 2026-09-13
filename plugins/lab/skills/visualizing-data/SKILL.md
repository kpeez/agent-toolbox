---
name: visualizing-data
description: Design or review statistical plots and plotting code for honest scales and accessibility. Not for conversational diagrams, simulations, or UI mockups.
---

# Visualizing data

Design or review plots and plotting code that make the intended comparison
clear, statistically honest, self-contained, and accessible. This skill is for
statistical plots, dashboards, and scientific figures. It is not for
conversational diagrams, simulations, or UI mockups.

## Frame the task

Before choosing or changing a chart, identify the exact question, audience,
variables, units, x-axis ordering, and whether uncertainty, missingness, or
sample size materially affect interpretation. If the request is vague, state
the inferred analytical task in one sentence.

## Choose and encode

Use the simplest chart that makes the intended comparison easy. Load
[chart selection](references/chart-selection.md) when the chart family is not
obvious or the data semantics need a closer match. A small label or annotation
edit does not require repeating chart-family selection.

Prefer position on a common scale and length over angle, area, volume, or hue
when quantitative precision matters. Load [perceptual rationale](references/tufte-perception.md)
when the encoding or visual scaffolding needs justification.

Keep scales, baselines, and transformations meaningful and explicit:

- bars on linear scales start at a meaningful zero;
- log-scaled bars need an explicitly labeled, meaningful baseline; otherwise
  use points or another encoding that does not imply one;
- use lines only for ordered axes;
- avoid dual axes, 3D effects, shadows, gradients, and decorative textures by
  default;
- prefer aligned comparisons, direct labels, sorted categories, and small
  multiples when they improve reading.

## Make it honest and accessible

Make the figure self-contained with a useful title or caption, labeled axes and
units, and source, timeframe, transformation, threshold, outlier, or regime
notes when they affect interpretation. Show uncertainty, missingness, or
distributional structure when omitting it would mislead.

Do not rely on color alone. Pair color with shape, line type, marker form, or
direct labels when categories matter, and keep essential marks legible against
the background. Load [color and accessibility](references/color-accessibility.md)
when palette, contrast, grayscale, or color-vision concerns are relevant.

## Review the result

When the task changes rendered visual output, inspect the rendered result at
the intended display size. Load [the review checklist](references/review-checklist.md)
for the final pass after drafting a plot or plotting script. Apply it when the
figure itself changes; a code-only label or formatting edit can use the
affected checks.

When creating or revising a plot, briefly state why the chart fits the question
and note material trade-offs such as truncated axes, log scaling, normalization,
uncertainty treatment, or accessibility constraints. Tufte minimalism removes
friction, not useful context; comparison clarity takes priority over novelty.
