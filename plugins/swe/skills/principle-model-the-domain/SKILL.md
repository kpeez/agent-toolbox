---
name: principle-model-the-domain
description: "When you write stateful logic, or code branches a lot or repeats a shape assumption across files, encode the domain in a data structure instead of scattered conditionals."
disable-model-invocation: true
---

# Model the domain

Encode the real domain in a data structure instead of scattering it across
conditionals. A structure that matches the domain makes invalid states
unrepresentable and deletes branches. Choosing it at write time is cheap.
Recovering it later reads as a refactor and gets deferred.

First, name the core data, its states, the legal transitions, and the owner of
each piece of state. Then trace how the code reads and writes the data.

Reach for:

- A state machine instead of scattered booleans, phases, or lifecycle checks.
- A typed model instead of loose parameters or repeated shape assumptions.
- A map, registry, lookup table, or discriminated union instead of branching
  spread across files.
- A reducer or command and event model instead of ad hoc state mutations.
- A module organized around one body of domain knowledge instead of a
  sequence such as load, validate, transform, and save. Execution order is not
  ownership.
- A small module boundary that gathers repeated behavior, ownership, or
  invariants.
- A queue, cache, index, graph, tree, or normalized collection where the
  access pattern calls for it.
- Any other structure that fits. When none fits, work out what the code must
  never allow and how the data gets read, then find the structure that
  encodes exactly that.

Do not force an abstraction. Prefer boring code when the current shape is
already clear, local, and unlikely to grow. Be skeptical of an abstraction
that adds indirection without removing branches, duplicated rules, invalid
states, or lifecycle risk.

You skipped this when a new feature grows an existing if/else chain by
one more branch, or when a second boolean must stay in sync with the first.
Temporal decomposition is another sign. Phase-named modules repeat the same
domain rules across steps.

For type-level encoding, see [type-system-discipline](../principle-type-system-discipline/SKILL.md).
