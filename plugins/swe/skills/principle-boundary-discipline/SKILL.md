---
name: principle-boundary-discipline
description: "When you wire validation, error handling, or framework adapters, concentrate guards at system boundaries, trust internal types, and keep business logic in pure functions."
disable-model-invocation: true
---

# Boundary discipline

Validate, narrow types, and handle errors where data crosses a system boundary
(CLI arguments, config files, external APIs, network). Inside, trust the
types. Do not validate again, and do not add redundant null checks. Parse raw
data into domain types at the boundary. Keep transport and framework types out
of the public surface. Business logic lives in pure functions with no
framework dependencies. The shell that calls them is thin.

Two tests:

- Is this data crossing a boundary right now? If not, the validation is
  redundant.
- Can this be a pure function that the shell just calls? If yes, extract it.

For the types themselves, see
[type-system-discipline](../principle-type-system-discipline/SKILL.md).
