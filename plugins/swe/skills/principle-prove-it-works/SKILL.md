---
name: principle-prove-it-works
description: "Before you claim that a task is done or a change works, check the real artifact through its real entry point and give a VERIFIED, NOT VERIFIED, or INCONCLUSIVE verdict."
disable-model-invocation: true
---

# Prove it works

Verify every task output by checking the real thing directly. Do not infer
from proxies, self-reports, or "it compiles".

Unverified work has unknown correctness. Indirect checks, such as file
timestamps, output freshness, agent self-reports, a passing unit test, or a
cached screenshot, feel cheaper than direct observation. Acting on a wrong
inference costs far more than checking the source.

## Check the real thing, not a proxy

- Check process liveness directly, not through derived state.
- Read the actual value, not a cached or derived representation.
- When verification fails, suspect the observation method before you suspect
  the system.

## Drive the real surface

1. Look for the project's verification skill, a project-local skill, usually
   `verify-<app>`, with a feature map. When one exists, use its Launch,
   Doctor, Drive, Evidence, and Cleanup sections, and the feature-map entry
   for the changed feature.
2. Find the real entry point that a user or caller uses, such as the CLI
   command, the HTTP endpoint, the browser page, the job runner, or the public
   API.
3. Run the change through it with an input that exercises the changed
   behavior. Read the actual output, value, or state.

## Script the check when you can

The strongest proof is a deterministic script that reruns the same
comparison, not a one-time look. Write the script, run it, and keep its
command and output as an artifact that a reviewer can rerun instead of
trusting your word.

Keep the artifact visible to the human. Commit it only for large or complex
work where the trail must be auditable later, like a big port or migration.
The `log-decisions` skill keeps that trail.

## Give one verdict

- **VERIFIED** means that you observed the expected behavior on the real
  surface.
- **NOT VERIFIED** means that you observed wrong behavior, or the check
  failed.
- **INCONCLUSIVE** means that you could not reach the real surface, or the
  observation cannot tell success from failure. Say what blocked it.

INCONCLUSIVE is not a pass. Report a negative verdict as plainly as a positive
one.

## Keep the verification skill current

When no verification skill exists and you improvised the drive, say once in
your reply that the `verification-skill` skill (`/verification-skill`, or
`$swe:verification-skill` in Codex) would make the drive reusable. Do not run
it yourself.

When a feature-map entry is wrong about a feature the change touched, or the
change adds or changes a user-facing feature, add or update that entry. It is
documentation that the change made obsolete. For wider drift, suggest the
`verification-skill` skill to the user.

Distinct from [explain-the-number](../principle-explain-the-number/SKILL.md), which checks what a measured
number means.
