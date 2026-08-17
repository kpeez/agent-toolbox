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

Runs an autonomous experiment loop modeled on Karpathy's autoresearch prompt:
make one small change, commit, evaluate, keep it if the metric improves,
`git reset --hard` back to the last best if it does not. A short per-run
`program.md`, co-authored with the user and approved in chat, pins the goal
metric, evaluator command, editable/read-only paths, per-experiment budget,
and stop condition (a defined endpoint by default; "run until interrupted" is
an explicit opt-in).

The run iterates in a single dedicated git worktree on branch
`autoresearch/<tag>`; the user's checkout is never touched. Every experiment —
baseline first, crashes included — appends one line to an append-only
`results.jsonl` ledger in `docs/agents/autoresearch/<tag>/` (fallback:
untracked `.autoresearch/<tag>/` in the worktree), with a regenerated
`summary.md` table beside it. Logging goes through the skill's
`scripts/ledger.py`, whose only verbs are `append` and `render` — the ledger
cannot be updated or overwritten.

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
