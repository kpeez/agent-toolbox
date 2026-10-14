---
name: principle-subtract-before-you-add
description: "When you sequence an addition, a refactor, or a rewrite, remove dead code, redundant checks, and stub references first, then build on the simpler base."
disable-model-invocation: true
---

# Subtract before you add

When you evolve a system, remove complexity first, then build. Default to
subtraction.

Make simplification a continual investment. Leave the design slightly simpler,
and more capable behind the same or a smaller surface, than you found it.

- Sequence removal before construction.
- Cut before you polish. Get to the minimum before you invest in quality.
- Design for observed use, not for speculative edge cases.
- Add no validator, parser, or guard beyond what the spec demands.
- Simplify prompts. Remove redundant instructions and excess templates.
- When a file, section, or reference has no unique content, delete it. Do not
  leave a stub.

Leave clear, proportionate code alone. Do not invent changes to satisfy this
rule.

In the result, name what you deleted or simplified, or say that the change
needed no subtraction. For the size of the change itself, see the
[laziness-protocol](../principle-laziness-protocol/SKILL.md).
