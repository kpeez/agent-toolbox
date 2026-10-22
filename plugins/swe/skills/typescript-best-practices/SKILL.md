---
name: typescript-best-practices
description: "TypeScript best practices. Use when reading or editing any .ts or .tsx file."
paths: ["**/*.ts", "**/*.tsx"]
---

# TypeScript best practices

Apply the `principle-type-system-discipline` skill first.

| Rule | Summary |
|------|---------|
| Discriminated unions | Model variants with a `kind` literal discriminant so impossible states cannot be represented. No bags of optional fields. |
| Branded types | Brand primitives with `& { readonly __brand: "X" }` so they cannot be mixed up. Validate once at the boundary. A brand comes from a verifying type guard (`input is AgentId`), never from `as`. |
| Constructive modeling | Build the shape so the illegal value cannot be constructed. `[T, ...T[]]` for non-empty, `[T, T][]` for even length, `start` plus `duration` for a range. Not a runtime guard, and not a wish for refinement types. |
| Simplest total type | Keep `T[]` while every operation on it stays total. Strengthen to `NonEmpty<T>` only where the loose type forces `!`, a cast, or a "should never happen" throw. |
| `unknown` over `any` | External data is `unknown`. |
| Schemas before guards | Before you hand-write a property-by-property type guard, use the repository's runtime schema library and infer the type from the schema, such as `z.infer`. |
| No `as` casts | Every `as` is a runtime crash waiting to happen. Cast only after validation. |
| Narrowing hierarchy | Discriminant switch, then the `in` operator, then `typeof` or `instanceof`, then a user-defined type guard, then `as` as the last resort. |
| Type guards | A guard must verify its claim. A lying guard is worse than `as`, because the bug hides behind a name that says it is safe. Name guards `isX` or `hasX`. |
| Exhaustiveness | Put `const _exhaustive: never = x;` in default arms so the compiler errors when a new variant is added. |
| `satisfies` over `as` | It validates the value without widening literal types. |
| Boundary validation | Parse where data crosses in, into a named domain type. `Record<string, unknown>`, however spelled, stops at that parse. Trust types inside. See the `principle-boundary-discipline` skill. |
| Schema-derived types | Reach for `Pick`, `Omit`, `Parameters`, `ReturnType`, `Awaited`, and `typeof` before you declare a new interface. |
| Object args | Pass objects, not positional arguments, so argument order documents itself. Skip this on hot paths (per-frame render, tokenizers, parsers). |
| Real tests | Do not mock what you can run. Prefer the framework's real test primitives with leak and disposable checks, and verify UI in a running build. Mock only what you cannot run locally. See the `testing-code` skill. |
| Structured telemetry | Prefer structured logger diagnostics with enough context to debug from an id. No `console.log` in shipped code. |

Examples: [patterns](references/patterns.md).
