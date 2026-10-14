---
name: principle-boundary-discipline
description: "When you wire validation, error handling, or framework adapters, concentrate guards at system boundaries, trust internal types, and keep business logic in pure functions."
disable-model-invocation: true
---

# Boundary discipline

Place validation, type narrowing, and error handling at system boundaries.
Trust internal code. Business logic lives in pure functions. The shell is
thin and mechanical.

Scattered validation is noisy and redundant, and it gives a false sense of
safety. Keep logic out of framework wiring so that you can test it without the
framework.

## Pattern

- **At boundaries** (CLI arguments, config files, environment variables,
  request payloads, files, database rows, external APIs, network protocols),
  parse raw input into domain types, validate it, return clear errors there,
  and handle failures defensively.
- **Inside the system**, pass typed data and propagate errors. Do not check
  again what the boundary already proved. Trust the types.
- **Across the boundary**, expose domain concepts, not the boundary's private
  representation. Keep general-purpose mechanism inside and special-purpose
  policy at the edge.

## Applications

Validation and error handling:

- Validate config at parse time (the boundary), not inside business logic.
- Parse raw data into domain types at the boundary.
- Do not re-export transport, storage, framework, or wire types through the
  public surface.
- Add no redundant null checks deep in call chains when the boundary already
  validated.

Code organization:

- Put business logic in pure functions with no framework dependencies.
- Write parse functions as pure transforms from raw bytes to typed state.
- Build prompts from structured state in, string out.
- Write scoring and assessment as pure transforms from state to results.

## Tests

- "Is this data crossing a system boundary right now?" If not, a new check
  here is redundant.
- "Can this be a pure function that the shell just calls?" If yes, extract
  it.

For the types themselves, see [type-system-discipline](../principle-type-system-discipline/SKILL.md).
