# CONTEXT.md Format

`CONTEXT.md` is a **committed**, repo-root domain glossary — and nothing else.
Not a spec, not a scratch pad, not a place for implementation decisions (those go
in `docs/agents/adrs/`). It pins down the project's vocabulary so terminology doesn't
drift across sessions. Create it lazily, only when the first term needs resolving.

It is optional. Most small changes never touch it. It earns its place when a
project has overloaded or ambiguous domain terms — common in ML/research work
(episode vs rollout vs trajectory, run vs experiment vs sweep, reward vs return,
eval split vs holdout).

## Structure

```md
# {Project / Context Name}

{One or two sentence description of what this project is about.}

## Language

**Run**:
A single training or evaluation invocation with one config.
_Avoid_: job, trial

**Experiment**:
A named group of runs that together answer one question.
_Avoid_: sweep (a sweep is one kind of experiment), study

**Return**:
The discounted sum of rewards over an episode.
_Avoid_: reward (reward is per-step), score
```

## Rules

- **Be opinionated.** When multiple words exist for one concept, pick the best and list the rest under `_Avoid_`.
- **Keep definitions tight.** One or two sentences. Define what it IS, not what it does.
- **Only project-specific terms.** General programming concepts (timeouts, error types, caching) don't belong even if used heavily. Ask: is this unique to this project's domain, or general? Only the former.
- **Group under subheadings** when natural clusters emerge; a flat list is fine otherwise.

This repo uses a **single** root `CONTEXT.md` — the multi-context `CONTEXT-MAP.md`
pattern (one glossary per package in a monorepo) is intentionally not adopted.
