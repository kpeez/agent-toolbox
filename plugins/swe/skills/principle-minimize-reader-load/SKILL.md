---
name: principle-minimize-reader-load
description: "When you review or shape code that is hard to trace, count the layers a reader must follow and the state they must hold, then collapse wrappers and shrink mutable scope."
disable-model-invocation: true
---

# Minimize reader load

Maintainability is the work a reader must do to understand code. Track two
axes.

- **Layers to trace** are the indirections between the question and the
  answer.
- **State to hold** is the hidden or mutable context that the reader must keep
  in mind.

Line counts, cyclomatic complexity, and "clean architecture" are proxies.
Reader load is the thing that matters. The two axes are independent. A flat
file with 50 globals can be as hard to reason about as a six-layer adapter
stack. Guard both. This is the human analog of
[guard-the-context-window](../principle-guard-the-context-window/SKILL.md). Working memory is finite for readers too.

- **Collapse layers** that cost more than they save. Examples are a wrapper
  with one caller, an adapter with one implementation and no external contract
  or test substitute behind it, and speculative indirection that nothing
  needed. Inline them.
- **Make adjacent layers change the abstraction.** A layer that repeats the
  methods and arguments of the next layer adds load without compression.
  Collapse pass-through layers.
- **Demand interface compression.** A broad interface over little logic makes
  readers learn both the surface and the implementation. Prefer boundaries
  that hide real decisions.
- **Shrink state scope.** Prefer pure functions (return values over
  mutation), locals over fields, fields over module state, and module state
  over globals. Derive a value instead of keeping two copies in sync.
- **Name the invariant at the boundary**, not in every consumer, so that the
  reader learns it once.
- Before you add a layer or a piece of state, check that it removes at least
  as much load elsewhere.

The test is whether a new reader can answer "where does X come from?" and "what can change
X?" in under 30 seconds. If not, cut layers or cut state.
