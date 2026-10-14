---
name: principle-outcome-oriented-execution
description: "During a planned rewrite or migration with explicit phase boundaries, converge on the target architecture instead of keeping intermediate states smooth with throwaway compatibility code."
disable-model-invocation: true
---

# Outcome-oriented execution

Optimize for the intended, verifiable end state, not for smooth intermediate
states.

Keeping every intermediate step fully stable often creates temporary
compatibility code that becomes long-lived debt. Converge on the target
architecture and prove correctness at explicit verification boundaries.

## Core rule

- Put end-state integrity before transitional stability.
- Intermediate breakage is acceptable when it is planned, scoped, and
  reversible.
- Do not write throwaway compatibility code only to keep an intermediate step
  smooth.

## Guardrails

- Use this only for planned rewrites and migrations with explicit phase
  boundaries.
- Declare where temporary breakage is acceptable.
- Keep high-signal checks on the areas you touch while you migrate.
- Require full static and runtime verification when the plan completes, per
  [prove-it-works](../principle-prove-it-works/SKILL.md).

For an internal API with old callers, see
[migrate-callers-then-delete-legacy-apis](../principle-migrate-callers-then-delete-legacy-apis/SKILL.md).
