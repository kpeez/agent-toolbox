# Applied ML Documentation Patterns

Use these patterns for experiment plans, evaluation reports, model changes,
dataset changes, training recaps, error analysis, and research summaries.

## Experiment Plan

```md
# <Experiment Name>

## Hypothesis

## Change

## Primary Metric

## Guardrails

## Dataset / Split

## Command

## Stop Conditions
```

Name the control, the changed variable, and the expected direction of movement.

## Experiment Result

```md
# <Experiment Name> Result

## Verdict

## Metric Comparison

## Slice / Error Analysis

## Reproducibility

## Decision

## Follow-ups
```

Lead with the verdict: keep, discard, inconclusive, or needs rerun.

## Metric Comparison

Use tables with direction, gate, and sample context.

```md
| Metric | Direction | Baseline | Candidate | Delta | Gate | Result |
| --- | --- | ---: | ---: | ---: | --- | --- |
| Macro F1 | higher | 0.781 | 0.812 | +0.031 | >= 0.800 | pass |
| P95 latency | lower | 142 ms | 177 ms | +35 ms | <= 180 ms | pass |
```

Always include:

- dataset and split
- sample count
- evaluator version or command
- prompt/config version when relevant
- confidence interval or repeated-run spread when available
- whether higher, lower, or target-range is better

Never imply that a positive delta is good without directionality.

## Slice And Error Analysis

Use grouped tables for regressions and examples for qualitative failures.

```md
| Slice | Baseline | Candidate | Delta | Notes |
| --- | ---: | ---: | ---: | --- |
| minority_language=sw | 0.74 | 0.68 | -0.06 | release-blocking |
| minority_language=tl | 0.71 | 0.70 | -0.01 | monitor |
```

For examples:

```md
| Input | Expected | Baseline | Candidate | Error Type |
| --- | --- | --- | --- | --- |
| ... | approve | approve | reject | false negative |
```

Redact sensitive content and mark truncation explicitly.

## Reproducibility Receipt

Record enough for another agent or human to rerun the result.

```md
## Reproducibility

- Commit: `<sha>`
- Command: `<exact command>`
- Config: `<path>`
- Dataset: `<name/version/split>`
- Seeds: `<seed list>`
- Environment: `<lockfile, image digest, or hardware note>`
- Outputs: `<artifact paths>`
```

Show missing fields as `Missing:` rather than omitting them.

## Model And Dataset Notes

For model changes, capture:

- base model or previous model
- training data and filtering changes
- objective or prompt changes
- eval summary and known regressions
- intended use and non-use
- limitations and safety notes
- license or access constraints

For dataset changes, capture:

- source and collection method
- filters and transformations
- row counts and split counts
- label distribution
- missingness, duplicates, and leakage checks
- sensitive fields and redaction
- intended use and known bias

## Charts And Images

Use generated image files when they materially improve review. Always include a
caption and the data or command used to produce the chart.

Good chart uses:

- training curves
- calibration plots
- ROC/PR curves
- label or slice distributions
- latency distributions
- confusion matrices

Do not include decorative charts or screenshots that cannot be traced back to
data or a command.
