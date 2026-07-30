# lab plugin

Research skills: an autonomous experiment loop for open-ended engineering or
research work, and research-backed guidance for data visualization. No agents,
hooks, or scripts — the plugin is two skills.

## Contents

```text
plugins/lab/
└── skills/
    ├── autoresearch/          # SKILL.md
    └── data-viz/              # SKILL.md + references/
```

## Skills

### `autoresearch`

Runs an autonomous experiment loop, inspired by Andrej Karpathy's autoresearch
loop but intentionally generic: define what success means and when to stop,
try one idea at a time, measure it, keep what helps, discard what does not,
and preserve the reasoning trail.

The loop never starts without a defined endpoint. Before any changes, the
skill pins down (using `/sharpen` when the goal is vague or high-stakes):

- **primary metric** — what improves, and in which direction
- **guardrail metrics** — what must not regress
- **acceptance threshold** — when a result is good enough
- **measurement command or review method** — how each experiment is scored
- **constraints** — time, cost, complexity, compatibility, safety
- **stop conditions** — when to stop and ask instead of continuing

Runs are isolated in a dedicated git worktree. Each experiment is stored under
a named group in a configurable artifacts root with its result recorded, so
useful changes are kept, failed directions are discarded, and the trail of
what was tried survives the run.

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
