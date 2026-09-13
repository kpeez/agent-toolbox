---
name: codebase-design
description: Evaluate module boundaries and interfaces using depth, information hiding, and caller complexity. Use for substantive interface design.
---

# Codebase Design — deep modules

The goal of module design is **depth**: a lot of behavior behind a small
interface. The vocabulary below supports precise reasoning; use the project's
established terms when they communicate the design more clearly.

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

## Design for testability

Consider, rather than assume, whether the design should:

- accept dependencies at the boundary instead of creating them internally;
- return computed results where that makes the behavior easier to observe; and
- hide incidental complexity such as retries, device placement, or tokenization
  behind a small interface.

Choose these trade-offs from the real callers, side effects, and external
contracts. A pure function or injected dependency is not automatically a better
seam.

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

For restructuring *existing* shallow modules — dependency categories, seam
selection, interface alternatives — use `/improve-codebase-architecture`; this
skill is for designing new interfaces as you build.
