# Applied ML Documentation Blocks

Use these blocks for experiment plans, evaluation reports, model and dataset
changes, training recaps, error analysis, and deployment reviews.

## Initial ML Blocks

### 1. `MetricDelta`

Compare baseline and candidate metrics with directionality, gates, uncertainty,
sample count, and evaluation provenance.

```mdx
<MetricDelta
  baseline="eval/base.json"
  candidate="eval/candidate.json"
  primary="macro_f1"
  gate="macro_f1 >= 0.81; p95_latency_ms <= 180"
/>
```

Requirements:

- Declare higher-is-better, lower-is-better, or a target range.
- Show absolute and relative deltas.
- Show confidence intervals or repeated-run dispersion when available.
- Distinguish threshold failure from statistical uncertainty.
- Preserve dataset, split, evaluator, prompt, sample count, and run identity.

### 2. `EvaluationTable`

Support sortable, filterable error and slice analysis with a path back from
aggregates to individual examples.

```mdx
<EvaluationTable
  src="eval/predictions.parquet"
  view="errors"
  groupBy="error_type,language"
  columns="input,expected,predicted,score,error_type"
/>
```

Support typed text, image, audio, label, probability, token, and link cells.
Expose truncation and redaction. Allow baseline/candidate rows to be compared and
selected rows to be exported.

### 3. `RunCard`

Record an experiment's hypothesis and reproducibility receipt.

```mdx
<RunCard
  id="exp-042"
  status="completed"
  hypothesis="Longer warmup reduces minority-class instability."
  command="uv run train.py --config configs/exp-042.yaml"
  commit="9e3a1c7"
  environment="uv.lock"
  seeds="17,29,43"
  inputs="dataset:claims-v5"
  outputs="model:classifier-v12; eval:exp-042"
/>
```

Show changed variables, controls, code revision, environment, seeds, hardware,
input and output artifacts, duration, and cost. Render missing reproducibility
fields as missing rather than silently omitting them.

### 4. `ArtifactCard`

Use one block with a strict schema selected by `kind`.

```mdx
<ArtifactCard kind="model" src="cards/model-v12.yaml" />
<ArtifactCard kind="dataset" src="cards/claims-v5.yaml" />
```

Model cards should cover intended use, limitations, base model, training data,
parameters, evaluation, license, and provenance. Dataset cards should cover
collection, composition, transformations, splits, licensing, sensitive fields,
biases, and intended use.

### 5. `Chart`

Use a constrained declarative chart grammar with a tabular fallback.

```mdx
<Chart
  src="eval/by-step.csv"
  mark="line"
  x="step:quantitative"
  y="loss:quantitative"
  color="run:nominal"
/>
```

Start with line, bar, point, histogram, heatmap, ROC/PR, and calibration views.
Require labels, units, sample definitions, and accessible colors. Do not permit
embedded JavaScript.

## Useful Combinations

- **Experiment plan:** `RunCard` + `Decision` + `Diagram` + metric gates
- **Experiment recap:** `MetricDelta` + `EvaluationTable` + `Chart` + `Aside`
- **Model change:** `Compare` + `Diff` + `ArtifactCard` + `MetricDelta`
- **Dataset revision:** `Diff kind="dataset-summary"` + `ArtifactCard`
- **Implementation spec:** `FileTree` + `AnnotatedCode` + `Questions`

## Later ML Blocks

- `DistributionDiff`: drift, missingness, quantiles, and effect thresholds
- `TraceViewer`: LLM, RAG, and agent spans, retrieval, tools, latency, tokens,
  cost, and evaluator annotations
- `SweepExplorer`: parameter importance, parallel coordinates, and Pareto fronts
- `ThresholdExplorer`: threshold-dependent confusion, cost, precision/recall,
  and subgroup effects
- `MediaComparison`: synchronized images, overlays, bounding boxes, and audio
- `EmbeddingExplorer`: projections, clusters, nearest neighbors, and linked rows
- `LineageGraph`: jobs, runs, datasets, models, and derived artifacts
- `ResourceProfile`: throughput, latency, memory, accelerator use, energy, cost

Keep notebook execution out of the initial protocol. Execution, environment
pinning, caching, security, and reproducibility require a separate design.
