---
name: principle-migrate-callers-then-delete-legacy-apis
description: "When a new internal API or module shape replaces an old one while old callers still exist, migrate every caller and delete the old API in the same wave."
disable-model-invocation: true
---

# Migrate callers then delete legacy APIs

When a new API is the right design, migrate the callers and remove the old API
in the same refactor wave. Do not keep compatibility layers.

Keeping both old and new APIs creates dual-path complexity, slows cleanup, and
makes the codebase feel append-only.

## Rule

1. List every caller of the old path, including code, scripts, configs, docs,
   and tests.
2. Move each caller to the new path.
3. Delete the old path, its aliases and adapters, and the tests that protect
   only its pre-refactor implementation. Make the remaining tests assert the
   new contract.
4. Search again for the old names to show that no caller remains.

Do not keep a legacy path only because internal callers still use it. A
temporary adapter is an exception, not the default architecture. Give it a
reason and a removal point.

## When this applies

- No external user depends on backward compatibility.
- The project can absorb coordinated breaking changes.
- The new API is part of a simplification or refactor.

When an external user depends on the old path, such as a published API, a file
format, or a CLI, its removal is a breaking change that needs approval.

For the phase plan of a larger rewrite, see
[outcome-oriented-execution](../principle-outcome-oriented-execution/SKILL.md).
