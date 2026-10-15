---
name: principle-migrate-callers-then-delete-legacy-apis
description: "When a new internal API or module shape replaces an old one while old callers still exist, migrate every caller and delete the old API in the same wave."
disable-model-invocation: true
---

# Migrate callers then delete legacy APIs

- Make the tests assert the new contract. Delete the tests that protect only
  the pre-refactor implementation.

## When this applies

- No external user depends on backward compatibility.
- The project can absorb coordinated breaking changes.
- The new API is part of a simplification or refactor.

When an external user depends on the old path, such as a published API, a file
format, or a CLI, its removal is a breaking change that needs approval.

For the phase plan of a larger rewrite, see
[outcome-oriented-execution](../principle-outcome-oriented-execution/SKILL.md).
