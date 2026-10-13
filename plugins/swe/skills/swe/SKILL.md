---
name: swe
description: "Route a software task to its playbook and track every step."
disable-model-invocation: true
argument-hint: "<task>"
---

# swe: route a task to its playbook

Task: $ARGUMENTS

When the task line is empty or still holds an unreplaced placeholder, the task
is the user's current request.

Relative paths in this file resolve against this skill's base directory: the
"Base directory for this skill" line at the top of this body or, when that
line is absent, the directory that holds this `SKILL.md`. The Read tool does
not resolve them for you: build the absolute path from that directory, then
read it.

## Match

1. Match again each time this skill is invoked and whenever the user says
   "new task". Do not continue an earlier playbook silently.
2. Observe any fact you need to choose a playbook: read code or run a
   command. Ask the user only for a choice that no observation can settle.
3. When one skill owns the whole task, use its line in
   [Single-skill routes](#single-skill-routes).
4. Otherwise, pick the first playbook in [Playbooks](#playbooks) whose line
   fits. The list runs from narrow to broad.
5. For large, ambiguous, or cross-session work, or work for another agent,
   propose a plan. When the user agrees, read and follow
   [write-plan](../write-plan/SKILL.md). For several PRs, then read and follow
   [to-issues](../to-issues/SKILL.md).
6. When nothing fits, say so in one line and use the skill that fits as a
   route. Do not invent a playbook.
7. Say `Playbook: <slug>. Reason: <one clause>.` or, for a route,
   `Route: <skill>. Reason: <one clause>.`

## Track

1. For a playbook, read `playbooks/<slug>.md` in full. A limit in its Reply
   line, such as "No PR", holds for the whole task. For a route, load the
   skill. Its numbered steps are the steps; when it has none, its section
   headings are. Each step's title is its handle.
2. When the host has a task-list tool, create one task per step right after
   you read the playbook. Copy each step line byte for byte, with its handle,
   in file order, and add task-specific tasks after them.
3. End your final reply with a "Steps" section that gives every handle in
   order with its state. A step you did not do is `skip:` with its reason:

   ```text
   1-reproduce-failure: done
   7-check-blast-radius skip: the change keeps the public signature
   ```

4. Before a step, load each name in its parentheses that you have not loaded
   in this session. The loaded skill's rules win over the step text.

Load a name this way:

- A swe skill, such as `diagnose`: the Skill tool, as `swe:diagnose`.
- A principle slug, such as `fix-root-causes`: the Skill tool, as
  `swe:principle-fix-root-causes`. The principle slugs are
  `subtract-before-adding`, `ancillary-fixes`, `verify-on-real-surface`,
  `fix-root-causes`, `model-the-domain`, `parse-at-boundaries`,
  `minimize-reader-load`, `sequence-verifiable-units`,
  `migrate-callers-then-delete`, `idempotent-operations`,
  `separate-shared-state`, and `explain-measurements`.
- [ship-pr](../ship-pr/SKILL.md), [write-plan](../write-plan/SKILL.md), and
  [to-issues](../to-issues/SKILL.md): read the `SKILL.md` by its absolute
  path. Never call the Skill tool on these three; the host blocks the call.
- `reviewer agent`: start the swe reviewer agent as a subagent and give it the
  step's criteria. When the step gives none, brief it as the independent
  reviewer line in [implement](../implement/SKILL.md#plans-and-issues) says.
- A playbook slug: read `playbooks/<slug>.md` as reference for that step. Its
  steps do not join the list, and the step text sets the scope.
- A skill of another plugin, such as `lab:autoresearch`: the Skill tool, by
  that name.

Where the host has no Skill tool, read the skill's `SKILL.md` instead.

## Authority

- Read [ship-pr](../ship-pr/SKILL.md) before the first commit. Its rules
  govern each commit, push, and pull request. Merge and release effects follow
  [ci-and-landing](../ci-and-landing/SKILL.md).
- When publication is authorized, open a draft PR at the first meaningful
  commit and push checkpoints during the work. The final `publish-draft-pr`
  step updates that PR; it is not the first push.
- Ask before a history rewrite, deleting a branch or data, or a write to a
  tracker or chat.

## Principles

Load a principle before you apply it. In the final reply, name each principle
that changed a decision and the choice it changed. Cite only principles you
loaded in this session.

## Playbooks

- `land-verified-pr`: mark ready and merge a verified PR.
- `drive-pr-to-green`: conflicts, review threads, and CI on an open PR.
- `diagnose-only`: explain a failure, crash, hang, leak, or captured trace; no fix requested.
- `fix-bug`: a reported defect to reproduce, root-cause, and fix.
- `improve-performance`: a measured slowness to improve against a baseline.
- `audit-tests`: prune or review an existing test suite.
- `evaluate-agent-change`: measure how a skill or prompt change affects agent behavior.
- `author-skill`: write or edit a skill, `AGENTS.md`, or `CLAUDE.md`.
- `review-architecture`: propose deepening refactors; no implementation.
- `refactor-structure`: change structure, keep behavior.
- `build-feature`: new or changed behavior.
- `investigate-question`: a read-only question with a cited answer, including "why was this built this way".

## Single-skill routes

- Design or judge a new test or a disposable probe: `testing-code`.
- Settle a design fork by running a throwaway sketch: `testing-code`.
- Conflicts in an active merge, rebase, or cherry-pick: `merge-conflicts`.
- Find what a change could break: `blast-radius`.
- Stress-test a plan or design: `grill`.
- The user corrects a mistake agents have made before: `correct`.
- Delegate to an external provider the user named: `external-subagents`.
- Sustained optimization of one metric: `lab:autoresearch`, when installed.

## Reply

Give the playbook slug or route, then what the playbook's Reply line asks
for or, for a route, the skill's own report. Then give the principle
citations. End with the "Steps" section. Label each piece of evidence with the
scale of the skill that produced it.
