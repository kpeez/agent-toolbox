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
5. Otherwise, pick the first playbook in [Playbooks](#playbooks) whose line
   fits. The list runs from narrow to broad.
6. Large or cross-cutting work, work the user steps away from, or work that no
   playbook fits goes to `figure-it-out`. It writes a bespoke playbook in the
   same step format. A standing multi-day program goes to `run-program`.
7. Say `Playbook: <slug>. Reason: <one clause>.` or, for a route,
   `Route: <skill>. Reason: <one clause>.`

## Track

1. For a playbook, read `playbooks/<slug>.md` in full. A limit in its Reply
   line, such as "No PR", holds for the whole task. For a route, load the
   skill. Its numbered procedure is the steps; a numbered list of criteria,
   levels, or rungs is not a procedure. When the skill has modes, use the
   procedure of the mode that fits the task. When the chosen skill or mode has
   no numbered procedure, its section headings are the steps. Each step's
   title is its handle.
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
- A skill of another plugin, such as `lab:autoresearch`: the Skill tool, by
  that name.

Where the host has no Skill tool, read the skill's `SKILL.md` instead.

## Triggers

These hold in every playbook and route, in addition to the steps.

- Your first message on a task: tell the user, in your own words, their goal,
  the problem they solve, and, when the task ships a change, the smallest
  change you expect to meet it (`in-your-own-words`). Do not wait for
  confirmation. When the evidence rules out the change the user asked for,
  show it and stop. Restate the goal in each subagent brief, and open each
  PR's `## Why` with it. Open each final report with it too, except after a
  fully specified one-line edit.
- Any code: name the data shape first, and choose its structure per
  `model-the-domain`.
- A nontrivial change, an architecture decision, or "are we sure?": run `how`
  over the affected subsystem first.
- Code that crosses a function boundary: run `architect` before you build.
- A contested design: give the design and its evidence to a `reviewer agent`
  before you ship.
- A fork you want to ask about ("which approach", "what should this do"):
  classify it first. When a run can show the answer (behavior, timing,
  layout, output, performance), it is not the user's question. Settle it with
  the `build-prototype` playbook. In a read-only investigation, answer from
  the evidence instead. Ask the user only a product or preference call that
  no experiment can settle (`never-block-on-the-human`).
- Initial scope or design that rests on a product or preference decision
  the user has not made: `interview-user` on those decisions only.
- Nontrivial multi-step work: write the throughput checkpoint
  (`build-feature` step 5).
- Parallel fan-out: `swarm`. OpenCode workers the user asked for: `opencode`.
- Any prose surface, the reply included: `writing`. It routes each surface
  (docs, skills, PR bodies, handoffs, plans, replies) to its rules. Write
  replies to the user and agent-facing text in ASD-STE100 Simplified
  Technical English.
- Before review: `no-comments` over the diff.
- A number you measured (a speedup, a regression, latency, an eval result):
  `benchmark-checklist` before you report or act on it.
- A PR-status request ("check on PR X", "get it green", "address the review
  comments"): the `babysit-pr` playbook. Opening a PR does not start it.
- A request to land or ship a green stack: the `ship-stack` playbook. Green is
  not safe. Nothing lands before an independent verdict per PR.
- A review bot commented: triage each finding on its merits per the
  [bot triage](../ship-pr/references/bot-triage.md) rules.
- A broken skill found mid-task: fix it in its own PR. Do not block, and do
  not silently work around it.
- Long, autonomous, or multi-phase work, or work the user steps away from:
  keep a decision trail with `log-decisions`.

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
  repeated across files. Encode the domain in a structure.
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

- The chat that runs this skill owns the playbook, the task list, and every
  spawn. Do not spawn a subagent to run the playbook itself.
- Code delegates: the `daedalus` agent (Claude Code: Agent tool,
  `swe:daedalus`; Codex: the `daedalus` agent). Give it this file's absolute
  path, the step, the file paths, the named data shape, and the success check.
- Search, review, and verification: native subagents. A reviewer gets the
  [review brief](../../references/review-brief.md).
- Match the model to the job. In Claude Code, use `opus` for judgment, prose,
  and the hardest code (cross-cutting design, concurrency, subtle
  algorithms); `sonnet` for routine code; `haiku` for mechanical edits. In
  Codex, raise or lower reasoning effort the same way.
- A second opinion is the same brief on a different model: another Claude
  model, or OpenCode through `opencode` when the user asked for it. Agreement is a strong
  signal.
- Fresh subagents by default. A fix round, a retry, or a follow-up goes to a
  fresh subagent with the full scope: the original brief, every later
  directive, and the prior agent's report and branch. Resume an agent only
  when the work needs state that lives in it, such as uncommitted changes or a
  running process.
- You own every subagent's work. Read the diff and write your own summary. Do
  not pass a subagent's report through.

## Writing the reply

Write the reply clean as you draft it. A cleanup pass after drafting does not
remove these patterns.

- Short declarative sentences. One thought per sentence.
- No long dash character. No colon as a mid-sentence connector; a colon before
  a list is fine.
- Terse is not an excuse to drop content. Keep every section the playbook's
  Reply line names: details, tradeoffs, choices, and open decisions.
- Name who the work is for and what changes for them before implementation
  detail. Then say what the next maintainer inherits.
- Never invent a link, citation, or transcript reference. Link only what you
  produced or read in this session.
- Every claim carries its evidence or its label in the same sentence. Never
  hand the user a check you could run.

## Comments

Write comments clean as you go. Keep a comment only for a non-obvious why that
the code cannot show. Scripts and tests get no comments that narrate phases;
the assertion or log string documents the step. This holds for every file you
produce, a delegate's diff included.

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
- `ship-stack`: verify a green stack independently, then land the contiguous
  verified run bottom-up.

Long runs and sessions:

- `run-autonomously`: a long task to drive to a checkable exit condition
  without stopping.
- `plan-multi-phase`: work that spans phases or stacked PRs. The plan is the
  deliverable.
- `autopilot-full`: a queue of independent PRs run to merged, one owner per
  PR.
- `autopilot-stack`: autopilot-full without the merge. Verified PRs the user
  lands, stacked only where one builds on another.
- `run-program`: a standing multi-day program with many PRs and subagents
  under one coordinator.
- `pick-up-session`: resume a prior agent's in-flight work from its handoff
  file, decision log, transcript, or branch.
- `pause-safely`: stop in-flight work cleanly so a new session can resume it.
- `clean-worktrees`: reclaim disk from merged or abandoned git worktrees.

## Single-skill routes

- Explain a failure, crash, hang, or leak; no fix requested: `diagnose`.
- Explain how a subsystem works, no code change: `how`.
- Design or judge a new test or a disposable probe: `testing-code`.
- Prune or review an existing test suite: `testing-code`.
- Explore competing designs before code: `architect`.
- Propose deepening refactors; no implementation: `codebase-design`.
- Write or edit a README, a docs page, or other prose: `writing`.
- Conflicts, review threads, or CI on an open PR, or mark ready and merge a
  verified PR: `ship-pr`.
- Find what a change could break: `blast-radius`.
- Settle open decisions in a plan or design with the user: `interview-user`.
- Write the work's current state for a new session: `handoff`.
- Catch the user up after time away: `ketchup`.
- The user corrects a mistake agents have made before: `correct`.
- Review a session for agent mistakes: `reflect`.
- Run OpenCode workers the user asked for: `opencode`.
- Build or audit the project's own skill that drives its app for
  verification: `verification-skill`.

## Reply

Give the playbook slug or route, then what the playbook's Reply line asks
for or, for a route, the skill's own report. Then give the principle
citations. End with the "Steps" section. Give each claim the confidence
label its skill defines: VERIFIED, NOT VERIFIED, or INCONCLUSIVE for a
change; a why tier for a rationale claim; a blast-radius rung for a safety
fact; and reproduced, inferred from the evidence, or unresolved for a
failure's cause.
