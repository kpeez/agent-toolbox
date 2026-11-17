---
name: architect
description: "Sketch types, signatures, and module structure before code. Use for 'architect this', or code that crosses a function boundary where jumping to code would lock in the wrong shape."
argument-hint: "<feature or interface>"
disable-model-invocation: true
---

# Architect

1. `1-trace-the-systems`: Before you write code, trace every system the
   change touches.
2. `2-sketch-two-shapes`: Sketch two different shapes for it (types,
   signatures, module boundaries).
3. `3-pick-the-shape`: Pick the shape where each piece of state has one owner,
   each task has one way to do it, and callers need to know least. For a large
   or contested design, use the design mode of the
   [codebase-design](../codebase-design/SKILL.md) skill instead of sketching
   alone.
4. `4-redesign-on-repeat-workarounds`: If workarounds repeat during the build,
   redesign instead of patching.
