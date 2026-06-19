# Core Rich-Documentation Blocks

Use this vocabulary across specs, plans, architecture notes, reports, and
recaps. The order reflects expected review value, not visual prominence.

## Promotion Rule

Keep content in Markdown unless a block provides machine-validatable structure,
specialized review behavior, stable annotations, meaningful alternate exports,
or semantics that survive a different renderer.

## Initial Blocks

### 1. `Compare`

Show before/after states or competing alternatives side by side. Prefer this to
generic columns because the relationship survives mobile, Markdown, and PDF
exports.

```mdx
<Compare kind="before-after">
<Case label="Before">

The evaluator averages every task equally.

</Case>
<Case label="After">

The evaluator weights tasks by production traffic.

</Case>
</Compare>
```

### 2. `Diff`

Compare code, config, prompts, schemas, dependencies, or structured data. The
renderer should support side-by-side and unified views and ignore meaningless
JSON/YAML key reordering.

```mdx
<Diff kind="prompt" before="prompts/v3.txt" after="prompts/v4.txt" />
```

### 3. `Decision`

Capture a choice, status, rationale, alternatives, and consequences. Durable
repository decisions still belong in ADRs; this block makes the decision
reviewable where it is discussed.

```mdx
<Decision status="proposed">

### Store evaluation examples as Parquet

- **Why:** typed columns and efficient slice queries
- **Alternative:** JSONL
- **Consequence:** preview tooling must read Parquet

</Decision>
```

### 4. `AnnotatedCode`

Connect commentary to validated line ranges instead of making the reviewer
cross-reference prose manually.

```mdx
<AnnotatedCode path="src/eval/scorer.py" lines="18-46">
<Annotation lines="22-27">Normalizes per-task scores before aggregation.</Annotation>
<Annotation lines="39-44">Fails the run when required slices are absent.</Annotation>
</AnnotatedCode>
```

### 5. `Diagram`

Render inert textual diagrams with a static fallback. Use for architecture,
control flow, state transitions, and data lineage. Start with Mermaid but retain
a normalized graph when nodes need links or annotations.

```mdx
<Diagram kind="flow">

dataset:raw -> transform:clean -> dataset:train
dataset:train -> train:finetune -> model:candidate
model:candidate -> eval:offline -> report:metrics

</Diagram>
```

### 6. `FileTree`

Show repository structure or a proposed change set with per-path status and
notes. Plain fenced trees are sufficient when paths do not need annotations.

```mdx
<FileTree root="src/eval">

modify | scorer.py        | Add slice-aware aggregation
add    | calibration.py   | Compute expected calibration error
add    | test_scorer.py   | Cover absent required slices

</FileTree>
```

### 7. `Questions`

Make unresolved decisions explicit and reviewable. Answers should serialize into
source rather than live only in UI state.

```mdx
<Questions>
<Question id="metric-gate">Should latency be a hard gate or a reported metric?</Question>
<Question id="slice-policy">Which production slices are release-blocking?</Question>
</Questions>
```

### 8. `Aside`

Use one semantic callout block with a closed `kind` enum: `note`, `warning`,
`risk`, `tip`, or `success`. Prefer a Markdown blockquote when no structured kind
or annotation behavior is needed.

```mdx
<Aside kind="risk">

The baseline and candidate were evaluated with different tokenizer revisions.

</Aside>
```

## Later Blocks

Add these only after real documents show demand:

- `Tabs`: interchangeable variants, files, or runtime states
- `DataModel`: entities, fields, keys, and relationships
- `Endpoint`: request and response contracts
- `Wireframe`: declarative interface structure
- `ReviewDecision`: approve, reject, or request changes as explicit source state

Do not add generic `Card`, `Grid`, `Stack`, `Row`, `Badge`, or `CustomHtml`
blocks. They make agents design presentation instead of expressing meaning.
