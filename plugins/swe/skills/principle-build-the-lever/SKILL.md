---
name: principle-build-the-lever
description: "When work is not trivial, such as edits, a migration, an analysis, or a check, build the script, codemod, or generator that does it or proves it instead of working by hand."
disable-model-invocation: true
---

# Build the lever

When the work is not trivial, build the tool that does it instead of doing it
by hand.

A lever is a codemod, a generator, a script, a query, or a rerunnable check.
It does the work the same way every time and reruns for free. A reviewer can
read it and rerun it to check the work. Hand-done changes can only be
re-verified by redoing them. A deterministic script turns "trust me" into "run
this".

Default to building the lever. Skip it only when the task is trivial, a couple
of obvious edits that you can check at a glance.

1. Do the first unit by hand to learn the recipe.
2. Write the lever. Rerun it on that unit and diff its output against your
   hand edit. The diff is empty when the lever is correct.
3. Make the lever safe to rerun, per [make-operations-idempotent](../principle-make-operations-idempotent/SKILL.md).
4. Run it on the remaining units, and check each unit per
   [sequence-verifiable-units](../principle-sequence-verifiable-units/SKILL.md).
5. Commit the lever when the work outlives the session.

Pick the lever for the job. Use a codemod or script for edits, a generator for
repetitive files, a dump-to-sqlite query for analysis, and a rerunnable check
for verification.

A deterministic lever beats fan-out. When the tool can process every unit in
one pass, run it yourself. Do not fan out subagents to hand-apply what a
script can do. When subagents do share the work, write the lever as a skill
that they all read. Put the recipe, the verification contract, and the files
they must not touch in that one document. Keep it outside the subagents' write
scope so that they cannot quietly edit the contract.

The bar is triviality, not repetition. A one-off still earns a lever when the
lever is what makes the work checkable. Per the [laziness-protocol](../principle-laziness-protocol/SKILL.md),
build the smallest script that does or proves the job, never a framework.

Applying this principle produces a file. If you cite it and the diff or the
report holds no codemod, script, generator, or subagent skill, you did not
apply it.

Distinct from [encode-lessons-in-structure](../principle-encode-lessons-in-structure/SKILL.md), which makes a recurring
instruction a durable guardrail. This principle is throughput and
reviewability on the work in front of you. For scripting the verification
itself, see [prove-it-works](../principle-prove-it-works/SKILL.md).
