---
name: principle-build-the-lever
description: "When work is not trivial, such as edits, a migration, an analysis, or a check, build the script, codemod, or generator that does it or proves it instead of working by hand."
disable-model-invocation: true
---

# Build the lever

When the work is not trivial, build the tool that does it instead of doing it
by hand. The tool is a codemod, a script, a generator, or a rerunnable check.
The bar is triviality, not repetition. Skip the tool only for a couple of
obvious edits.

- Do the first unit by hand. Then build the tool and prove it by rerunning it
  on that unit. Make it safe to rerun, per
  [make-operations-idempotent](../principle-make-operations-idempotent/SKILL.md).
- A deterministic tool beats fan-out. When you do fan out, write the recipe,
  the verification contract, and the files to leave alone as one skill. The
  delegates read it and cannot edit it.
- Applying this principle produces a file. If the diff holds no script,
  codemod, generator, or delegate skill, you did not apply it. Commit the file
  when the work outlives the session.
- Build the smallest script that does or proves the job, never a framework.
