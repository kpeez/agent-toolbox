---
name: implement
description: "Implement an authorized feature or fix through relevant verification. Use for scoped code changes."
argument-hint: "<feature or fix>"
---

# Implement

Implement one authorized, scoped task through proportionate evidence and
verification. Read the task and relevant current state before acting. Preserve
unrelated work and the user's authority boundaries. This skill's job is the
smallest justified code change with evidence.

## Contract

1. Make the smallest justified change. Before you add code, a layer, or a
   special case, follow
   [subtract-before-you-add](../principle-subtract-before-you-add/SKILL.md).
   When the work has several steps, such as a sweep or a migration, follow
   [sequence-verifiable-units](../principle-sequence-verifiable-units/SKILL.md).
   When the change adds a migration, job, retry, or resume path, follow
   [make-operations-idempotent](../principle-make-operations-idempotent/SKILL.md).
2. For a reported defect, find the cause with
   [diagnose](../diagnose/SKILL.md) before you change code, and rerun its
   reproduction after the fix. Before you apply the fix, and after a fix
   fails, follow [fix-root-causes](../principle-fix-root-causes/SKILL.md).
3. Choose evidence by behavioral risk. Before your first edit, write one
   `Check:` line: the entry point you will drive, the command you will run,
   and the result that would show the change is wrong. A static check, reproducible demonstration, existing
   workflow, or explicit no-permanent-test decision is often enough. Before adding or rewriting a permanent test, or when behavior
   is uncertain or a probe is requested, pass the `testing-code` admission
   gate. Before claiming the change works, follow
   [prove-it-works](../principle-prove-it-works/SKILL.md).
4. Run relevant repository gates and behavior-specific checks. Do not
   special-case a test or a check to make it pass; report it. A failing
   required gate blocks completion and publication, but continue authorized
   diagnosis and correction when that can resolve the failure. When you find an
   issue outside the task, such as an unrelated baseline failure, follow
   [ancillary-fixes](../principle-ancillary-fixes/SKILL.md).
5. Report the change, the evidence, and unresolved concerns. Give one
   `Verification:` line with the entry point, the exact command you ran
   (pipes included), and the result you observed. Name a check you could not run as not run.

## Documentation completion

An authorized code or convention change includes updating documentation that
it makes obsolete; do not ask separately. Find and update affected guidance in
repository docs, READMEs, linked project or vault notes, tracker descriptions,
and agent instructions. Follow each destination's authoring and access rules;
for a README or a docs page, follow `writing`. Replace stale guidance with
the current behavior; earlier rationale stays in the PR and the commit. Report any
affected documentation left stale and the reason.

## Plans and issues

- When the caller names a plan (for example
  `feature-export-json.plan.html`), read it first and work to it. Follow
  [plan storage](../../references/plan-storage.md) to find the plan file.
  If a material design choice changes during the work, update the
  plan.
- For work with an issue, include its key when creating a branch; preserve an
  established branch name. When the plan is agreed and the branch or worktree
  exists, move the issue from its backlog or todo state to the started state
  (In Progress in Linear). Never move an issue backward, and never change the
  status of an issue this work does not own. In a run with several owners,
  the coordinator owns the status. Ship-pr sets the later states. Comment on
  the issue only for a blocker or a decision that needs the user.
- For substantive changes, give an independent reviewer the actual diff,
  accepted requirements, and relevant verification evidence. Ask it to report
  only gaps in correctness or the stated requirements.

For substantial work with independently executable parts, fan it out with
[swarm](../swarm/SKILL.md) before implementation. The lead remains
responsible for decisions, integration, and final verification. A bounded
worker reports to its caller rather than dispatching more agents unless its
assignment authorizes that.
