---
name: autoresearch
description: Run an autonomous experiment loop for open-ended engineering or research work with a defined endpoint. Use when the user asks Codex to autoresearch, explore alternatives, improve toward a target metric, run repeated experiments, or compare outcomes. The skill helps define the goal and stop conditions, creates an isolated worktree, stores each experiment under a named group in specs/_experiments/<group-name>/, records results, keeps useful changes, and discards failed directions.
---

# Autoresearch

Run an autonomous experiment loop: define what success means and when to stop,
try one idea at a time, measure it, keep what helps, discard what does not, and
preserve the reasoning trail.

This is inspired by Andrej Karpathy's autoresearch loop, but is intentionally
generic. Adapt it to the current repository, domain, and measurement surface.

## Define the Endpoint

Before making changes, help the user define the target metric. A metric can be a
number, a test command, a benchmark, a rubric, a qualitative bar, or a concrete
observable outcome.

Use `/grill-me` when the goal is vague, high-stakes, or underspecified. Clarify:

- primary metric: what improves and in which direction
- guardrail metrics: what must not regress
- acceptance threshold: when the loop can call a result good enough
- measurement command or review method
- constraints: time, cost, complexity, compatibility, safety, UX, privacy
- stop conditions: when to stop and ask instead of continuing

Every autoresearch run needs a defined end state. Do not begin the loop until
the goal, primary metric, acceptance threshold, and stop conditions are clear.

## Isolate the Run

Run autoresearch on a dedicated worktree.

1. Inspect the current branch, base branch, and working tree.
2. Refuse to overwrite unrelated user changes.
3. Create or ask for an experiment group name, such as `api-latency`.
4. Create a branch named `autoresearch/<group-name>`.
5. Create a sibling worktree for that branch when the provider/workspace allows
   it. If worktrees are unavailable, stop and explain the limitation.
6. Create the group directory `specs/_experiments/<group-name>/` if it does not
   exist.
7. Run all experiments from that worktree.

Use the repository's normal private-spec setup if one exists. In agentspec-style
repos, ensure `specs/` is a private symlink before writing experiment records.

## Experiment Records

Store every experiment under a group directory named after the experiment
program:

```text
specs/_experiments/
└── <group-name>/
    ├── README.md          ← group-level overview
    └── YYYY_MM_DD-expt-<NN>-<expt-slug>/
        ├── README.md
        ├── LOG.md
        ├── logs/
        └── scripts/
```

The group name matches the branch suffix from `autoresearch/<group-name>` (e.g.,
`api-latency`). Use a monotonically increasing two-digit experiment number
within each group, such as `2026_05_24-expt-01-cache-key-rubric`.

The group-level `README.md` captures the shared context for the whole program:

```markdown
# <Group Title>

## Goal

## Primary Metric

## Guardrail Metrics

## Acceptance Threshold

## Stop Conditions

## Summary

| #   | Experiment | Result | Decision |
| --- | ---------- | ------ | -------- |
```

Update the summary table after each experiment completes.

Each experiment `README.md` should be short and structured:

```markdown
# <Experiment Title>

## Hypothesis

## Change

## Metric

## Result

## Decision

## Follow-ups
```

Use `LOG.md` for timestamped command history, observations, and links to files
under `logs/` or `scripts/`.

Keep one-off scripts, commands, raw outputs, screenshots, traces, or notes in
that experiment folder. Do not commit `specs/_experiments` unless the repository
explicitly tracks specs; in agentspec-style repos it is private context.

## Baseline

Create the group directory and write its `README.md` first. Then create the
first experiment folder for the baseline before changing code. Use a slug such
as `baseline` or `current-state`.

Record in the baseline experiment's `README.md`:

- current commit and branch
- metric definition and guardrails
- baseline measurement, if measurable
- known caveats or missing measurement tools

The baseline folder's `README.md` is the first record in the experiment series.
Later experiment folders should link back to the baseline when useful.

## Loop

After setup and metric definition are clear, iterate within the defined goal and
stop conditions.

1. Inspect the current branch, commit, latest experiment record, and
   `git status`.
2. Pick one clear experiment with a falsifiable hypothesis.
3. Create the next timestamped experiment folder.
4. Record the hypothesis and planned measurement in `README.md`.
5. Make the smallest code or workflow change that tests the idea.
6. Run the metric command or review method.
7. Save relevant logs and scripts into the experiment folder.
8. Record the result and decision: `keep`, `discard`, or `inconclusive`.
9. Keep the change only when it improves the primary metric without unacceptable
   guardrail regressions or complexity.
10. Continue from the kept best state until the acceptance threshold is met, the
    experiment budget is exhausted, or a stop condition triggers.

Prefer simple wins. A tiny improvement from brittle complexity is usually not
worth keeping; an equal outcome from simpler code usually is.

## Discarding Work

Discard only the current experiment's changes. Never reset or delete unrelated
user work. Follow the provider's approval policy for destructive commands.

When discarding an experiment:

- preserve the experiment folder and README
- record why it failed or was not worth keeping
- restore the worktree to the prior kept state
- carry forward any useful lesson into the next experiment record

## Reporting

Keep chat updates compact while the loop is running. Report:

- metric and current best result
- number of experiments run
- kept changes and discarded directions
- path to the latest experiment folder
- whether the defined endpoint was reached
- blockers or stop-condition triggers

Update the group-level `README.md` summary table after each experiment.
