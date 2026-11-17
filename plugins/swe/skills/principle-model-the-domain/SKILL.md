---
name: principle-model-the-domain
description: "When you write stateful logic, or code branches a lot or repeats a shape assumption across files, encode the domain in a data structure instead of scattered conditionals. In existing code, find implicit state machines and make them explicit."
disable-model-invocation: true
---

# Model the domain

Encode the domain in a data structure instead of scattering it across
conditionals. The right structure makes invalid states unrepresentable and
deletes branches.

Reach for these:

- A state machine instead of scattered booleans or phase checks.
- A typed model instead of loose parameters.
- A map, registry, or discriminated union instead of branching spread across
  files.
- A reducer instead of ad hoc mutations.
- An index, queue, or normalized collection where the access pattern calls for
  it.

Do not force it. Keep boring code when the shape is clear, local, and unlikely
to grow. Distrust an abstraction that adds indirection without removing
branches or invalid states.

The sign that you skipped this is a feature that grows an if/else chain by
one more branch, or a second boolean that must stay in sync with the first.

In existing code, look for a state machine nobody wrote down (flags that must
agree, a status string checked in several files, a bug that needs an event
sequence) before you add a branch, and encode it as one type or transition
table.

For type-level encoding, see
[type-system-discipline](../principle-type-system-discipline/SKILL.md).
