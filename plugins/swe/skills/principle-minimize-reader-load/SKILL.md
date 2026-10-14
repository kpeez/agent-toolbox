---
name: principle-minimize-reader-load
description: "When you add or review a layer, wrapper, or piece of state: count what a reader must trace and hold, and collapse layers that do not pay for themselves."
disable-model-invocation: true
---

# Minimize reader load

Reader load is the work a reader does to answer a question about the code. It
has two independent axes:

- **Layers to trace**: the indirections between the question and the answer.
- **State to hold**: the hidden or mutable context that the reader must keep in
  mind.

Line counts and complexity scores are only proxies.

- Collapse a layer that costs more than it saves, such as a wrapper with one
  caller, a layer that repeats the methods and arguments of the next layer, or
  an adapter with one implementation and no external contract or test
  substitute behind it.
- Prefer an interface that hides a real decision. A broad interface over
  little logic makes the reader learn both.
- Shrink the scope of state: return values over mutation, locals over fields,
  fields over module state, and module state over globals. Derive a value
  instead of keeping two copies in sync.
- State an invariant once, at the boundary, not in each consumer.
- Before you add a layer or a piece of state, check that it removes at least
  as much load elsewhere.

Test: can a new reader answer "where does X come from?" and "what can change
X?" in under a minute? If not, cut layers or state.
