---
name: principle-migrate-callers-then-delete
description: "When a new internal API or module shape replaces an old one: move every caller, then delete the old path and its tests in the same change."
user-invocable: false
---

# Migrate callers, then delete

When a new internal API or module shape replaces an old one, do not keep the
old path because callers still use it. Two paths double the code that readers
and maintainers must know.

1. List every caller of the old path: code, scripts, configs, docs, and tests.
2. Move each caller to the new path.
3. Delete the old path, its aliases and adapters, and the tests that protect
   only its implementation. Make the remaining tests assert the new contract.
4. Search again for the old names to show that no caller remains.

A temporary adapter is an exception. Give it a reason and a removal point.
Do not write throwaway compatibility code only to keep an intermediate step
smooth.

This rule covers internal paths. When an external user depends on the old
path, such as a published API, a file format, or a CLI, its removal is a
breaking change that needs approval.
