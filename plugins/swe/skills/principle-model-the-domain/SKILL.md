---
name: principle-model-the-domain
description: "Before you write stateful or branching logic: name the data shape, its states, and the owner of each, and pick a structure that cannot hold invalid states."
disable-model-invocation: true
---

# Model the domain

Choose the data shape before the logic. Encode the domain in a structure, not
in conditionals spread across files. The choice is cheap at write time and
expensive to recover later.

1. Name the core data, its states, the legal transitions, and the owner of each
   piece of state.
2. Trace how the code reads and writes the data. Pick the structure that fits
   the main access paths and cannot hold an invalid state:
   - a state machine or tagged union instead of booleans that must stay in
     sync;
   - a typed model instead of loose parameters or a shape assumption repeated
     across files;
   - a table, map, or registry instead of a branch chain;
   - a module that owns one body of domain knowledge, not one phase of a
     pipeline such as load, validate, and save.
3. Keep plain code when the current shape is clear, local, and unlikely to
   grow. An abstraction must remove branches, duplicated rules, invalid states,
   or lifecycle risk.

Signs that you skipped this: a new feature adds one more branch to an if/else
chain, or a second boolean must stay in sync with the first.
