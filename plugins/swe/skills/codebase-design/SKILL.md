---
name: codebase-design
description: Design a consequential new interface, or review existing module boundaries and propose deepening refactors that cut coupling and caller complexity. Report-only for reviews; implementation is separate.
---

# Codebase Design — deep modules

The goal of module design is **depth**: a lot of behavior behind a small
interface. The vocabulary below supports precise reasoning. Use the project's
established terms when they communicate the design more clearly.

Pick the mode:

- **Design a new interface** (you build or plan a new module): follow
  [Design mode](#design-mode).
- **Review existing modules** (find friction, propose deepening refactors):
  follow [Review mode](#review-mode).

## Vocabulary

- **Module** — anything with an interface and an implementation (function,
  class, package, slice).
- **Interface** — everything a caller must know to use the module correctly:
  types, invariants, ordering constraints, error modes, required config,
  performance characteristics. Not just the type signature.
- **Implementation** — the code inside.
- **Depth** — leverage at the interface: how much behavior a caller (or test)
  can exercise per unit of interface they must learn. **Deep** = high leverage.
  **Shallow** = interface nearly as complex as the implementation.
- **Seam** — where an interface lives; a place behavior can be altered without
  editing in place.
- **Adapter** — a concrete thing satisfying an interface at a seam.
- **Leverage** — the caller's benefit from depth; **locality** — the
  maintainer's: changes, bugs, and knowledge concentrated in one place.

**Depth is a property of the interface, not the implementation.**

## Key tests

- **Deletion test** — imagine deleting the module. If complexity vanishes, it
  was a pass-through. If complexity reappears across N callers, it was earning
  its keep.
- **The interface is the test surface.** Callers and tests cross the same seam;
  if a test bypasses it, check whether the test protects a real contract before
  deciding that the module needs reshaping.
- **Adapter count is evidence, not a rule.** Multiple justified adapters make a
  seam concrete; one adapter can still be warranted by a real external contract
  or a test substitute.
- **Reader load** — when you add or review a layer, wrapper, or piece of
  state, follow [minimize-reader-load](../principle-minimize-reader-load/SKILL.md).

## Design mode

Consider, rather than assume, whether the design should:

- accept dependencies at the boundary instead of creating them internally;
- return computed results where that makes the behavior easier to observe; and
- hide incidental complexity such as retries, device placement, or tokenization
  behind a small interface.

Choose these trade-offs from the real callers, side effects, and external
contracts. A pure function or injected dependency is not automatically a better
seam.

Before you write stateful or branching logic, follow
[model-the-domain](../principle-model-the-domain/SKILL.md). When data crosses a
system boundary, or you decide where validation goes, follow
[parse-at-boundaries](../principle-parse-at-boundaries/SKILL.md).

For a consequential new interface, map representative callers and the behavior
they need. Specify invariants, ordering, error modes, defaults, and costs before
choosing the surface. Show at least one caller use and explain what complexity
the implementation hides. Compare materially different interfaces only when a
real trade-off exists; use [interface design](references/interface-design.md)
for that comparison. Do not manufacture alternatives to an obvious interface.

## Review mode

Surface architectural friction and propose **deepening opportunities**:
refactors that turn shallow modules into deep ones. The aim is testability and
AI-navigability. A review reports only. It does not authorize implementation.

Follow these steps. Read [review details](references/review.md) for the
friction signals, the candidate fields, ranking, and the documentation rules.

1. `1-explore-friction`: Explore the requested area and its callers for
   friction.
2. `2-apply-deletion-test`: Apply the deletion test to each candidate module.
3. `3-report-candidates`: Report candidates with strength, or say no refactor
   is recommended.
4. `4-hash-out-chosen-design`: Settle a chosen design with the user before
   implementation. Use [hash-out](../hash-out/SKILL.md). Classify the dependencies
   of the chosen candidate with [deepening](references/deepening.md).

Reply with the report only. Implementation is a new task, routed to the
`refactor-structure` playbook of the `/swe` router.
