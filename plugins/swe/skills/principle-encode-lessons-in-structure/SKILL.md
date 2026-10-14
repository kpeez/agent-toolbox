---
name: principle-encode-lessons-in-structure
description: "When you catch yourself writing the same instruction a second time, or see a recurring correction, encode the rule as a lint, metadata flag, runtime check, or script instead of more text."
disable-model-invocation: true
---

# Encode lessons in structure

When an instruction repeats, the text is not working. Encode the rule as a
lint, a metadata flag, a runtime check, a type, or a script, so that the
environment enforces it.

If the lesson needs judgment and cannot be encoded, make the instruction more
prominent and add an example of the failure mode.

Corollary. If the fix is structural, use only the structural fix. The
instruction is the symptom.

The `correct` skill applies this principle to a repeated agent mistake.
