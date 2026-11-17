---
name: principle-type-system-discipline
description: "When you design types, review a function signature, or write code in a statically typed language, make the compiler reject impossible states, mixed-up primitives, and unhandled variants."
disable-model-invocation: true
---

# Type system discipline

Make the compiler reject impossible states, mismatched primitives, and
unhandled variants. For TypeScript syntax, see the
`typescript-best-practices` skill.

- **Brand semantic primitives.** If two arguments share a primitive type but
  mean different things, give each its own type. Validate once at creation.
- **External data is untyped until parsed.** JSON, RPC payloads, CLI
  arguments, config, environment variables, and database rows go through a
  parse function at the boundary that returns the typed model. See
  [boundary-discipline](../principle-boundary-discipline/SKILL.md).
- **Derive types from authoritative schemas.** When a schema file owns a
  shape, derive the type from it. Do not hand-roll a parallel one.
