---
name: principle-redesign-from-first-principles
description: "When you integrate a new requirement into an existing design, redesign as if the requirement had been a foundational assumption from the start instead of bolting it on."
disable-model-invocation: true
---

# Redesign from first principles

When you integrate a change, do not bolt it onto the existing design. Redesign
as if the requirement had been a foundational assumption from the start.

- Read all affected files and understand the current design.
- Ask "if we wrote this from scratch with this new requirement, what would we
  build?" Then check whether the current design already gives that. A
  no-change result is valid when it does.
- Propagate the change through every reference, including types, docs,
  examples, and rationale sections.
- Think through the whole redesign, then deliver it in increments, per
  [sequence-verifiable-units](../principle-sequence-verifiable-units/SKILL.md).

This is the method for preserving option value when you integrate a change
into an existing design. See [foundational-thinking](../principle-foundational-thinking/SKILL.md).
