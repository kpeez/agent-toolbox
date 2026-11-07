---
name: principle-model-the-domain
description: "When you write stateful logic, or code branches a lot or repeats a shape assumption across files, encode the domain in a data structure instead of scattered conditionals. In existing code, find implicit state machines and make them explicit."
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

## Find implicit state machines

Existing code often holds a state machine that nobody wrote down. Find
implicit state machines before you add a branch to stateful code, while you
debug a state bug, and in a design review. These signs show one:

- Two or more booleans or nullable fields where only some combinations are
  valid, such as `isLoading` and `error` both set.
- A `status`, `phase`, or `mode` string compared in more than one file.
- Guards that repeat one precondition, such as `if (!started || done) return`.
- A timestamp or nullable field used as state, such as `completedAt != null`
  meaning "done".
- Order kept by call sequence or a comment, such as "call `open` before
  `send`".
- Retry, resume, or cancel paths that each rebuild "where are we" from the
  data.
- A bug that needs a specific sequence of events to reproduce.

For each machine you find, write its states, its legal transitions, the event
that causes each transition, and the owner of the state. A pair of states with
no legal path between them, or a combination of fields that maps to no state,
is a bug or dead code. Then encode the machine as one explicit type or
transition table with the `refactor-structure` playbook. To check its rules
or show a bug as a path through the states, use the `statechart` skill.

For type-level encoding, see [type-system-discipline](../principle-type-system-discipline/SKILL.md).
