---
name: codebase-design
description: Shared vocabulary and principles for designing deep modules — substantial behavior behind small interfaces, positioned at clean seams. Use when designing a new module or interface, choosing where a seam or test surface goes, or judging whether a module is deep or shallow.
---

# Codebase Design — deep modules

The goal of module design is **depth**: a lot of behavior behind a small
interface. Use this vocabulary exactly — don't drift into "component,"
"service," "API," or "boundary."

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
  editing in place. (Use this, not "boundary.")
- **Adapter** — a concrete thing satisfying an interface at a seam.
- **Leverage** — the caller's benefit from depth; **locality** — the
  maintainer's: changes, bugs, and knowledge concentrated in one place.

**Depth is a property of the interface, not the implementation.**

## Design for testability

1. Accept dependencies as parameters rather than creating them internally.
2. Return computed results instead of performing side effects.
3. Minimize surface area: fewer methods, simpler parameters, more complexity
   hidden inside (retries, device placement, tokenization — callers shouldn't
   see any of it).

## Key tests

- **Deletion test** — imagine deleting the module. If complexity vanishes, it
  was a pass-through. If complexity reappears across N callers, it was earning
  its keep.
- **The interface is the test surface.** Callers and tests cross the same seam;
  if a test must bypass the interface to verify behavior, reshape the module.
- **One adapter = hypothetical seam. Two adapters = real seam.**

For restructuring *existing* shallow modules — dependency categories, seam
selection, interface alternatives — use `/improve-codebase-architecture`; this
skill is for designing new interfaces as you build.
