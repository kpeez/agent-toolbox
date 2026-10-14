---
name: principle-experience-first
description: "When a product, UX, or feature-scope tradeoff comes up, choose the user's experience over implementation convenience and ship fewer polished features over more rough ones."
disable-model-invocation: true
---

# Experience first

When implementation convenience conflicts with user delight, choose delight.

- Justify every feature, control, and option.
- Ship less, ship better. A polished experience with three features beats a
  rough one with ten.
- Prototype before you commit. A design decision is cheaper in throwaway HTML
  than in production code.
- Get the details right, such as transitions, alignment, spacing, feedback,
  and error states.
- Tighten the core loop. Every feature should serve the central workflow or
  get out of the way.

The user is whoever consumes the work. For a UI, that is the end user. For a
library or an internal API, it is the colleague who imports it. The engineer
who maintains the code next is a user too. Weigh their experience the same
way, and explain impact from their perspective.

Foundations should serve the experience. [foundational-thinking](../principle-foundational-thinking/SKILL.md)
governs the sequence of work. This principle governs the target.
