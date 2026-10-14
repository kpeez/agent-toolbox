---
name: principle-parse-at-boundaries
description: "When data enters the system or you place validation: parse it once at the edge into domain types, and trust those types inside."
disable-model-invocation: true
---

# Parse at boundaries

External data is untyped until you parse it: CLI arguments, config files,
environment variables, request payloads, files, database rows, and external
API responses.

- At the boundary, parse raw input into domain types, validate it, and return
  clear errors there.
- Inside, trust the parsed types. Do not check again what the boundary
  already proved.
- Keep special-purpose policy at the edge and general-purpose mechanism
  inside. Do not expose transport, storage, or wire types through the public
  interface.
- Give two meanings two types when they share a primitive, such as a user id
  and an order id.
- Match exhaustively on variants, so that an unhandled new variant fails the
  type check.
- Derive types from the schema that owns the shape (OpenAPI, protobuf, a
  database migration) instead of a parallel type written by hand.
- Do not cast past the type checker. Prove the fact at the boundary, or record
  the cast as a hazard.
- Strengthen a type only where a runtime check or a "cannot happen" error shows
  that it is too weak. Then stop.

Test: does this data cross a system boundary here? If not, a new check here is
redundant.
