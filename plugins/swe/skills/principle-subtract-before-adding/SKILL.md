---
name: principle-subtract-before-adding
description: "When a change would add code, a layer, a check, or a special case: prefer deleting, then simplifying, then optimizing, then automating; stop at the first that works. No change is a valid result."
disable-model-invocation: true
---

# Subtract before adding

Prefer deleting over simplifying, simplifying over optimizing, and optimizing
over automating. Stop at the first rung that reaches the intended outcome.

- State the intended outcome. Ask what you would build if the requirement had
  been there from the start, then check whether the current design already
  gives it. A no-change result is valid when the requested behavior already
  holds.
- Remove dead code, stale references, and redundant checks in the area first.
  Then build on the simpler base.
- Build for observed use. Add a validator, parser, guard, option, or layer only
  when the spec or a real caller needs it.
- Make each decision in one place and pass its result on. Do not repeat one
  choice at several sites.
- Make the smallest diff that solves the problem. Fewer lines beat elegant
  boilerplate.
- Delete a file, section, or reference that has no unique content. Do not
  leave a stub.

Leave clear, proportionate code alone. Do not invent changes to satisfy this
rule.

In the result, name what you deleted or simplified, or say that the change
needed no subtraction.
