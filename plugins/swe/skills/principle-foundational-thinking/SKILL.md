---
name: principle-foundational-thinking
description: "Before you write logic, choose the core types and data structures, decide what comes before what, and ask what concurrent actors share, so that the downstream code becomes obvious."
disable-model-invocation: true
---

# Foundational thinking

Structural decisions protect option value. Code-level decisions protect
simplicity.

**Data structures first.** Get the data shape right before you write logic.
Define the core types early, trace every access pattern, and choose structures
that match the dominant paths.

At code level, DRY the structure, not every line. Types and data models should
converge. Three similar statements still beat a premature abstraction. Prefer
explicit code over clever code. Test behavior and edge cases, not line counts.

**Concurrency corollary.** Before you share state between actors, ask "what
happens if another actor modifies this concurrently?" If the answer is not
"nothing", isolate the state, per
[separate-before-serializing-shared-state](../principle-separate-before-serializing-shared-state/SKILL.md).

**Scaffold first.** If something helps every later phase, do it first. Ask
"does every later phase benefit from this existing?" CI, linting, test
infrastructure, and shared types are scaffold. Sequence for option value, with
setup before features and tests before fixes. Keep commits small and
single-purpose.

Each increment should land a coherent abstraction or deepen one that exists.
Do not spread a new capability across callers as special-case coordination.

Subtraction comes before scaffolding. Remove dead code first, then lay
foundations, per [subtract-before-you-add](../principle-subtract-before-you-add/SKILL.md).
