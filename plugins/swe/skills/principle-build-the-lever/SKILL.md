---
name: principle-build-the-lever
description: "Before you make many similar edits, a migration, an analysis, or a check by hand: build the script, codemod, or generator that does it or proves it, so a reviewer can rerun it."
disable-model-invocation: true
---

# Build the lever

A lever is a small tool that does the work or proves it: a codemod, a script,
a generator, a query, or a rerunnable check. It does the work the same way
every time, and a reviewer can read and rerun it. Hand edits can only be
checked by doing them again.

Build a lever for any work that is not trivial. Skip it only for a few edits
you can check at a glance.

1. Do the first unit by hand to learn the recipe.
2. Write the lever. Rerun it on that unit and diff its output against your hand
   edit. The diff is empty when the lever is correct.
3. Make the lever safe to rerun, per
   [idempotent-operations](../principle-idempotent-operations/SKILL.md).
4. Run it on the remaining units, and check each unit per
   [sequence-verifiable-units](../principle-sequence-verifiable-units/SKILL.md).
5. Commit the lever when the work outlives the session.

Keep the lever the smallest script that does the job, per
[subtract-before-adding](../principle-subtract-before-adding/SKILL.md). When
one script can process every unit in one pass, run it yourself; do not fan out
subagents to make the same edits by hand. When subagents do share the work,
give them the recipe, the check, and the files they must not touch in one
document outside their write scope.

You applied this principle only when the diff or the report holds the lever.
