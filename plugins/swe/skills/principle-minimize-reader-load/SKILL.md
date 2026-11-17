---
name: principle-minimize-reader-load
description: "When you review or shape code that is hard to trace, count the layers a reader must follow and the state they must hold, then collapse wrappers and shrink mutable scope."
disable-model-invocation: true
---

# Minimize reader load

Reader load is the work a reader must do to understand code. It has two
independent axes. One is the layers to trace between the question and the
answer. The other is the hidden or mutable state to hold in mind. Guard both.

- Collapse layers that only forward, such as a wrapper with one caller, an
  adapter with no second implementation, or a pass-through method. Inline
  them.
- Shrink state scope. Prefer returns over mutation, locals over fields,
  fields over module state, and module state over globals. Derive a value
  instead of keeping two copies in sync.
- Name an invariant once at the boundary, not in every consumer.

Test: can a new reader answer "where does X come from?" and "what can change
X?" in under 30 seconds? If not, cut layers or cut state.
