---
name: principle-laziness-protocol
description: "When you refactor, size a diff, or want to add an abstraction, a layer, or a threaded signal, bias toward deletion and the smallest change that solves the problem."
disable-model-invocation: true
---

# Laziness protocol

Bias toward deletion and the smallest change that solves the problem.

- **Climb the ladder from the bottom.** Prefer deleting over simplifying,
  simplifying over optimizing, and optimizing over automating. Stop at the
  first rung that reaches the intended outcome. A no-change result is valid
  when the requested behavior already holds.
- **Consolidate decisions.** Do not repeat the same choice in several places.
  Put it behind one source of truth and pass the result on as a simple flag.
- **Minimize the diff.** Make the smallest change that solves the problem.
  Fewer lines beat elegant boilerplate.
- **Add structure only for a real need.** Add an abstraction, a layer, or a
  signal threaded through several calls only when a current caller needs it.

To remove weight before you build, see [subtract-before-you-add](../principle-subtract-before-you-add/SKILL.md).
