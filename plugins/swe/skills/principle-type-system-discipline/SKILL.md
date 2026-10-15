---
name: principle-type-system-discipline
description: "When you design types, review a function signature, or write code in a statically typed language, make the compiler reject impossible states, mixed-up primitives, and unhandled variants."
disable-model-invocation: true
---

# Type system discipline

Make the compiler reject impossible states, mismatched primitives, and
unhandled variants. Prefer defining errors and special cases out of existence
over adding handlers. For TypeScript syntax, see the
`typescript-best-practices` skill.

- **Brand semantic primitives.** `UserId` and `OrderId` are strings underneath
  but must not be interchangeable. Give each its own type, such as a branded
  intersection in TypeScript or a newtype elsewhere. Validate once at
  creation, and trust the type downstream. If two arguments share a primitive
  type but mean different things, brand them.
- **External data is untyped until parsed.** RPC payloads, JSON, IPC
  messages, CLI arguments, config files, environment variables, and database
  rows all need a parse function at the boundary that turns the input into the
  typed model. [boundary-discipline](../principle-boundary-discipline/SKILL.md) says where to put validation.
- **Derive types from authoritative schemas.** When a protocol buffer,
  OpenAPI spec, GraphQL schema, database migration, design-token file, or
  another file owns a shape, derive from it instead of writing a parallel type
  by hand. See [encode-lessons-in-structure](../principle-encode-lessons-in-structure/SKILL.md).
