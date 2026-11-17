---
name: principle-foundational-thinking
description: "Before you write logic, choose the core types and data structures, decide what comes before what, and ask what concurrent actors share, so that the downstream code becomes obvious."
disable-model-invocation: true
---

# Foundational thinking

Get the data shape right before you write logic. Define the core types early,
trace every access pattern, and choose structures that match the dominant
paths. DRY the structure, not every line.

Before you share state between actors, ask what happens if another actor
modifies it concurrently. If the answer is not "nothing", isolate it, per
[separate-before-serializing-shared-state](../principle-separate-before-serializing-shared-state/SKILL.md).

Scaffold first. Do first whatever helps every later phase (CI, tests, shared
types), after you remove dead code, per
[subtract-before-you-add](../principle-subtract-before-you-add/SKILL.md).
Keep commits small and single-purpose.
