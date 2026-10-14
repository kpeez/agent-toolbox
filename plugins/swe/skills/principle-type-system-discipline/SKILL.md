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

- **Make illegal states unrepresentable.** Model variants as sum types
  (discriminated unions, enums with payloads, sealed classes), not as a bag of
  optional fields where contradictory combinations compile.
  `{ completed: boolean; completedAt?: Date }` admits `completed: true` with
  no date. Derive the boolean from `completedAt`, or model
  `{ kind: 'open' } | { kind: 'done'; at: Date }`. If you can write a comment
  that explains when a combination of fields is valid, split it into a sum
  type.
- **Types are constructions, not restrictions.** Build the type up from the
  values you want instead of carving them out of a looser type with checks. A
  non-empty list is a head plus a rest. A valid time range is a start plus a
  duration. Choose the shape that cannot build the illegal value, and expose
  the interface that callers need on top.
- **Brand semantic primitives.** `UserId` and `OrderId` are strings underneath
  but must not be interchangeable. Give each its own type, such as a branded
  intersection in TypeScript or a newtype elsewhere. Validate once at
  creation, and trust the type downstream. If two arguments share a primitive
  type but mean different things, brand them.
- **External data is untyped until parsed.** RPC payloads, JSON, IPC
  messages, CLI arguments, config files, environment variables, and database
  rows all need a parse function at the boundary that turns the input into the
  typed model. [boundary-discipline](../principle-boundary-discipline/SKILL.md) says where to put validation.
- **Do not lie to the type system.** Casts, unsafe coercions, and assertion
  functions that bypass the compiler are latent runtime crashes. If the
  compiler cannot prove a fact, prove it (validate, narrow, refine the model)
  or record the cast as a hazard. Trace each `any`, `as`, or `assertNotNull`
  to the boundary and validate there.
- **Exhaustive matching is the compiler's job.** A match on a sum type must
  fail compilation when someone adds a variant without handling it, so that
  the compiler tells the next agent where to add a case. Use your language's
  idiom, such as a `never`-typed binding in TypeScript, an unannotated `match`
  in Rust, `-Wincomplete-patterns` in Haskell, or sealed-class match
  exhaustiveness in Kotlin.
- **Derive types from authoritative schemas.** When a protocol buffer,
  OpenAPI spec, GraphQL schema, database migration, design-token file, or
  another file owns a shape, derive from it instead of writing a parallel type
  by hand. See [encode-lessons-in-structure](../principle-encode-lessons-in-structure/SKILL.md).
- **Strengthen a type only where partiality appears.** A runtime assertion, a
  null check, or a "this should never happen" throw marks a place where a type
  is too weak. Push that check up into the type. Then stop. The type system
  tracks the cases that each use site must handle. It does not need to
  describe the data as precisely as possible. Prefer total functions. `sum` of
  an empty list is 0, so it takes the plain list. `head` of an empty list has
  no answer, so it demands the non-empty one. If nothing would otherwise
  panic, keep the plain type.
