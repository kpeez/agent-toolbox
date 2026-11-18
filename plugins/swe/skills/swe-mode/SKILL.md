---
name: swe-mode
description: "Route a software task to its playbook and track every step. Use for /swe:swe-mode, or when the user asks which swe workflow fits a task."
argument-hint: "<task>"
---

# swe-mode: route a task to its playbook

Task: $ARGUMENTS

When the task line is empty or still holds an unreplaced placeholder, the task
is the user's current request.

Relative paths in this file resolve against this skill's base directory: the
"Base directory for this skill" line at the top of this body or, when that
line is absent, the directory that holds this `SKILL.md`. The Read tool does
not resolve them for you: build the absolute path from that directory, then
read it. Put this file's absolute path in every delegate's brief.

## Match

1. Match again each time this skill is invoked and whenever the user says
   "new task". Do not continue an earlier playbook silently.
2. Run `go-deeper` on a new task, unless it already ran for this task or
   its skip rule applies. Match the rewritten task.
3. Observe any fact you need to choose a playbook: read code or run a
   command. Ask the user only for a choice that no observation can settle.
4. When one skill owns the whole task, use its line in
   [Single-skill routes](#single-skill-routes).
5. A queue of PRs to build goes to `autopilot-full` when the PRs are
   independent and should merge, and to `autopilot-stack` when they depend
   on each other or the user lands them. A dependent stack goes to
   `autopilot-stack` also when the user asks for the merge. That request is
   the operator's go, and the playbook lands the stack with `ship-stack`
   after its handoff. This step holds also when the user is away.
   A request to plan the queue only is not a build. It goes to
   `plan-multi-phase`.
6. Otherwise, pick the first playbook in [Playbooks](#playbooks) whose line
   fits the whole task. The list runs from narrow to broad. When that
   playbook is `fix-bug`, `build-feature`, or `refactor-structure` and the
   code change is large, cross-cutting, or a multi-day program, use
   `figure-it-out` instead. It writes a bespoke playbook in the same step
   format.
7. Work that no playbook fits also goes to `figure-it-out`.
8. Say `Playbook: <slug>. Reason: <one clause>.` or, for a route,
   `Route: <skill>. Reason: <one clause>.`

## Track

1. For a playbook, read `playbooks/<slug>.md` in full. A limit in its Reply
   line, such as "No PR", holds for the whole task. For a route, load the
   skill. Its steps are the list items that start with a handle
   (``1. `1-name`: ...``) and the headings that are a handle (`## 1-name`);
   other numbered lists are criteria, levels, or rungs, not steps. When the
   skill has modes, each mode has its own list under its heading: use the list
   of the mode that fits the task. Each step's title is its handle.
2. When the host has a task-list tool, create one task per step right after
   you read the playbook or load the routed skill. Copy each playbook step line
   byte for byte; for a routed skill, copy each handle with its first
   sentence. Keep file order, and add task-specific tasks after them.
3. End your final reply with a "Steps" section that gives every handle in
   order with its state. A step you did not do is `skip:` with its reason:

   ```text
   1-reproduce-failure: done
   7-check-blast-radius skip: the change keeps the public signature
   ```

4. Before a step, load each name in its parentheses that you have not loaded
   in this session. The loaded skill's rules win over the step text.

Load a name this way:

- A swe skill, such as `diagnose`: the Skill tool, as `swe:diagnose`. Some swe
  skills are hidden from the model's skill list. When the Skill tool refuses
  one, read `../<name>/SKILL.md` in full.
- A principle slug, such as `fix-root-causes`: read
  `../principle-fix-root-causes/SKILL.md` in full. Principles are not in the
  model's skill list. [Principles](#principles) lists the slugs.
- `reviewer agent`: start a fresh native subagent with the
  [review brief](../../references/review-brief.md) and the step's criteria.
  When the step gives none, brief it as the independent reviewer line in
  [implement](../implement/SKILL.md#plans-and-issues) says.
- A playbook slug: read `playbooks/<slug>.md` as reference for that step. Its
  steps do not join the list, and the step text sets the scope.

Where the host has no Skill tool, read the skill's `SKILL.md` instead.

## Triggers

These hold in every playbook and route, in addition to the steps.

- First message: restate the user's goal and the smallest change that meets
  it (`in-your-own-words`), then proceed. Open each subagent brief and final
  report with the goal. A PR body follows the
  [PR body template](../ship-pr/references/pr-body.md) and never names the
  requester or the chat.
- Starting any subagent: the first line of its brief is
  `Read <path>/worker.md before anything else.`, with `<path>` the absolute
  path of this skill's folder.
- A fork that a run can settle: prototype it with `build-prototype` instead of
  asking. A product or preference call no run can settle: `interview-user`.
- Code: name the data shape first (`model-the-domain`). Across a function
  boundary: `architect`. Fan-out: `swarm`, or `external-agents` when the user
  asked for another agent CLI. Contested design: a `reviewer agent`.
- Prose, the reply included: `writing`, in ASD-STE100 Simplified Technical
  English. Before review: `no-comments`.
- A number you measured: `benchmark-checklist`.
- PR status: the `babysit-pr` playbook. Landing a green stack: the
  `ship-stack` playbook.
- Review bot comments: judge each on its merits per
  [bot triage](../ship-pr/references/bot-triage.md).
- Long or unattended work: `log-decisions`.

## Principles

Read the leaf skill in full for any principle you apply. Each entry says when
it applies. The leaf is `../principle-<slug>/SKILL.md`.

**Core**

- `laziness-protocol`: refactoring, sizing a diff, or tempted to add
  abstractions or layers. Bias to deletion and the smallest change.
- `foundational-thinking`: before logic. Core types and data structures,
  scaffold-before-feature order, and what concurrent actors share.
- `redesign-from-first-principles`: a new requirement meets an existing
  design. Redesign as if it had been there from day one.
- `attack-the-premise`: two or more fixes that share one premise failed the
  same check. Write the premise down and test it before the next fix.
- `subtract-before-you-add`: sequencing an addition, refactor, or rewrite.
  Remove dead weight first.
- `minimize-reader-load`: code that is hard to trace. Count layers and hidden
  state, and collapse layers that do not pay for themselves.
- `outcome-oriented-execution`: planned rewrites and migrations. Converge on
  the target; keep no throwaway compatibility states.
- `experience-first`: product, UX, or scope tradeoffs. Choose the user's
  experience over implementation convenience.
- `exhaust-the-design-space`: a novel interaction or architecture with no
  precedent. Build 2 or 3 competing sketches and compare.
- `build-the-lever`: many similar edits, a migration, an analysis, or a check.
  Build the script, codemod, or generator a reviewer can rerun.

**Architecture**

- `model-the-domain`: stateful logic, heavy branching, or one shape assumption
  repeated across files. Encode the domain in a structure. In existing
  code, find implicit state machines and make them explicit.
- `boundary-discipline`: validation, error handling, or framework adapters.
  Guard at the system edge and trust internal types.
- `type-system-discipline`: types or signatures in a typed language. Make
  illegal states unrepresentable and parse external data at the edge.
- `make-operations-idempotent`: commands, jobs, retries, or resume paths.
  Converge to the same end state after a crash at any point.
- `migrate-callers-then-delete-legacy-apis`: a new internal API while old
  callers exist. Migrate and delete in one change.
- `separate-before-serializing-shared-state`: two actors could write the same
  file, branch, key, or object. Remove the sharing before you add a lock.

**Verification**

- `prove-it-works`: before you say a change works. Verify on the real
  artifact and give a VERIFIED, NOT VERIFIED, or INCONCLUSIVE verdict.
- `fix-root-causes`: debugging. Trace each symptom to the first place the
  system went wrong and fix it there. A guard is a fix only for a legitimate
  state.
- `sequence-verifiable-units`: multi-step work and how you stack commits and
  PRs. Check each unit before the next.
- `test-behavior-not-implementation`: writing, changing, or keeping a test.
  Assert what users observe: fail when behavior breaks, pass when internals
  change.
- `explain-the-number`: before you measure, and before you trust, report, or act on a measured number.
  Name what limits it, with run count and spread.

**Delegation**

- `guard-the-context-window`: large outputs, long files, or fan-out planning.
  Send bulk to subagents and keep summaries in the main thread.
- `never-block-on-the-human`: tempted to ask "should I do X?" on reversible
  work. Do it, report it, and let the user correct it.

**Meta**

- `encode-lessons-in-structure`: you write the same instruction a second
  time. Encode it as a lint, flag, check, or script instead.
- `ancillary-fixes`: you find an issue outside the task. Decide to fix it now
  or report it.

Only these are principles; another skill, such as `testing-code`, is not.

Load a principle before you apply it. In the final reply, name each principle
that changed a decision and the choice it changed. Cite only principles you
loaded in this session.

## Autonomy

- **Do it.** Load [ship-pr](../ship-pr/SKILL.md) before the first commit. Its
  rules govern each commit, push, pull request, merge, and release effect.
  Reversible work proceeds without asking: edit code, write a file, start a
  branch, start an eval. An implementation request also covers pushing your
  own branch, opening or updating a draft PR, and merging once the work is
  verified and checks pass, per ship-pr's Publication authority. A local-only
  request or an explicit hold point stops publication. Report what you did
  and why, so the user can correct it.
- **Always pause** before an irreversible write: a force-push to a shared
  branch, a history rewrite on a branch you did not create, a deploy, deleting
  a branch or data, or a message to people outside the project.
- **Session overrides.** "Don't stop", "going to bed", "run until done", or "be
  fully autonomous" means keep going. Decide each call the grant covers, act
  on it, and report it. For a call only the user can make, apply a default,
  report it, and say what the user could choose instead.
- When publication is authorized, open a draft PR at the first meaningful
  commit and push checkpoints during the work. The final `publish-draft-pr`
  step updates that PR; it is not the first push.
- **No is an acceptable answer.** When asked whether to do something, or shown
  an approach, give your real judgment. Decline or push back when the work
  does not earn its place. Agreement is not the default.

## Subagents

- The chat that runs this skill owns the playbook and every spawn. Do not
  spawn a subagent to run the playbook itself.
- Code delegates: the `daedalus` agent (Claude Code: Agent tool,
  `swe:daedalus`; Codex: the `daedalus` agent). Give it the step, the file
  paths, the named data shape, and the success check. Search, review, and
  verification: native subagents. A reviewer gets the
  [review brief](../../references/review-brief.md).
- Match the model to the job: the strongest model for judgment, prose, and
  the hardest code; a faster one for routine and mechanical work.
- Fresh subagents by default. A fix round, a retry, or a follow-up goes to a
  fresh subagent with the original brief, every later directive, and the
  prior agent's report and branch. Resume an agent only when the work needs
  state that lives in it, such as uncommitted changes or a running process.
- You own every subagent's work. Read the diff and write your own summary.

## Writing the reply

Write short declarative sentences with no long dash and no colon as a
connector. Lead with what changes for the user. Give each claim its evidence
or a label (measured, inferred, or guess). Never hand the user a check you
could run.

## Playbooks

Code and investigation:

- `fix-bug`: a reported defect to reproduce, root-cause, and fix.
- `improve-performance`: a measured slowness to improve against a baseline.
- `hillclimb-metric`: sustained improvement of one metric against a target,
  with one keep-or-revert decision per attempt.
- `diagnose-runtime`: diagnose a live runtime symptom (leak, spin, glitch)
  from instrumentation. No fix.
- `diagnose-trace`: diagnose a captured profile, trace, or heap snapshot. No
  fix.
- `evaluate-agent-change`: measure how a skill or prompt change affects agent
  behavior.
- `author-skill`: write or edit a skill, `AGENTS.md`, or `CLAUDE.md`.
- `build-prototype`: a throwaway sketch to settle a design or an empirical
  fork by observation.
- `match-visual-parity`: pixel-exact UI equivalence against a baseline.
- `refactor-structure`: change structure, keep behavior.
- `build-feature`: new or changed behavior.
- `investigate-question`: a read-only question with a cited answer, including
  "how does X work" and "why was this built this way".

PRs:

- `babysit-pr`: drive a PR or stack to merge-ready: conflicts, review
  threads, CI.
- `ship-stack`: verify a green stack independently, then land the full stack
  with `gh stack merge` or the contiguous verified run bottom-up.

Long runs and sessions:

- `run-autonomously`: one long task, not a queue of PRs, to drive to a
  checkable exit condition without stopping.
- `plan-multi-phase`: work that spans phases or stacked PRs. The plan is the
  deliverable.
- `autopilot-full`: a queue of independent PRs run to merged, one owner per
  PR.
- `autopilot-stack`: autopilot-full without the merge. Verified PRs the user
  lands, linked as a stack only where one builds on another. PRs that depend
  on each other come here also when the user asks for the merge. Then the
  playbook lands them with `ship-stack` after its handoff.
- `pick-up-session`: resume a prior agent's in-flight work from its handoff
  file, decision log, transcript, or branch.
- `pause-safely`: stop in-flight work cleanly so a new session can resume it.
- `clean-worktrees`: reclaim disk from merged or abandoned git worktrees.

## Single-skill routes

- Explain a failure, crash, hang, or leak; no fix requested: `diagnose`.
- Design or judge a new test or a disposable probe: `testing-code`.
- Prune or review an existing test suite: `testing-code`.
- Explore competing designs before code: `architect`.
- Propose deepening refactors; no implementation: `codebase-design`.
- Write or edit a README, a docs page, or other prose that is not a skill,
  `AGENTS.md`, `CLAUDE.md`, or a plan of PRs: `writing`.
- Conflicts, review threads, or CI on an open PR, or mark ready and merge a
  verified PR: `ship-pr`.
- Find what a change could break: `blast-radius`.
- Settle open decisions in a plan or design with the user: `interview-user`.
- Write the work's current state for a new session: `handoff`.
- Catch the user up after time away: `ketchup`.
- The user corrects a mistake agents have made before: `correct`.
- Review a session for agent mistakes: `reflect`.
- Run workers on another agent CLI the user asked for: `external-agents`.
- Build or audit the project's own skill that drives its app for
  verification: `verification-skill`.

## Reply

Give the playbook slug or route, then what the playbook's Reply line asks
for or, for a route, the skill's own report. Then give the principle
citations. End with the "Steps" section. Give each claim the confidence
label its skill defines: VERIFIED, NOT VERIFIED, or INCONCLUSIVE for a
change; a blast-radius rung for a safety fact; and reproduced, inferred from
the evidence, or unresolved for a failure's cause.
