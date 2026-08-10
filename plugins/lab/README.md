# lab plugin

Source-backed research, reproducible autonomous experiments, and
research-backed data-visualization guidance. Lab is four portable instruction
skills with no agents, hooks, runtime framework, or provider configuration.

## Contents

```text
plugins/lab/
└── skills/
    ├── research/              # SKILL.md + source protocol
    ├── deep-research/         # SKILL.md + evidence-packet schema
    ├── autoresearch/          # SKILL.md
    └── data-viz/              # SKILL.md + references/
```

## Skills

### `research`

Investigates one bounded question with one researcher and writes one cited
memo under `docs/agents/research/`. It prioritizes primary sources, reopens
citations to verify material claims, records unavailable evidence and
uncertainty, and treats fetched content as untrusted evidence rather than
instructions.

Use this path when the question is focused enough for one evidence-gathering
lane. Use `deep-research` when independent lanes or contradiction-focused
synthesis are required.

### `deep-research`

Coordinates broad source-backed work through bounded, non-overlapping,
read-only lanes. The coordinator writes a brief before dispatch, retains each
lane's evidence packet, deduplicates and reconciles the evidence, audits final
citations, and owns the sole final report (plus a proposal only when requested).

Web-only lanes receive no local workspace context without explicit user
authorization. Lane workers gather evidence but do not write files, commit,
push, log in, or take external actions. The skill uses safe host-native
delegation when available and the same lanes sequentially otherwise; Lab does
not ship a provider router or agent bridge.

### `autoresearch`

Runs a bounded autonomous experiment loop around an explicitly approved,
immutable `program.md`. Before candidate changes, the program and measured
baseline pin down:

- **primary metric** — what improves, and in which direction
- **guardrail metrics** — what must not regress
- **frozen evaluator** — the command and hash used for every measurement
- **acceptance threshold** — when a result is good enough
- **mutation boundary** — mutable paths, forbidden paths, and guardrails
- **budgets** — per-evaluation and total limits
- **stop conditions** — when to stop and ask instead of continuing

Runs are isolated in a dedicated git worktree. The baseline and every
one-hypothesis candidate are recorded in an append-only TSV ledger with detailed
private artifacts under `.autoresearch/<group>/`. Verified improvements are
kept; discarded or guardrail-regressing candidates return to the last verified
best commit without touching unrelated user work.

### `data-viz`

Guidance for designing, reviewing, and refining plots, charts, dashboards,
and scientific figures — used before choosing a chart type, while writing
plotting code (Python/R/JavaScript), and again as a review pass on the first
draft. The goal: plots that are honest, comparison-friendly, self-contained,
and accessible.

Detail loads on demand from the reference files:

| Reference                           | Covers                                              |
| ----------------------------------- | --------------------------------------------------- |
| `references/chart-selection.md`     | Picking the right chart form for the comparison     |
| `references/tufte-perception.md`    | Perception and data-ink principles                  |
| `references/color-accessibility.md` | Color use, palettes, and accessibility              |
| `references/review-checklist.md`    | The final critique pass for clarity and honesty     |
