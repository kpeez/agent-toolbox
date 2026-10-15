# swe

swe gives the agent one entry point for software work: a router that matches
your task to a playbook, runs each step with the skills and principles that
step needs, and ends with the evidence and the state of every step. The aim is
less code of higher quality, and work you can check without a replay of the
session.

## Install

Claude Code:

```text
/plugin marketplace add kpeez/agent-toolbox
/plugin install swe@agent-toolbox
```

Codex CLI:

```text
codex plugin marketplace add kpeez/agent-toolbox
codex plugin add swe@agent-toolbox
```

Start a new session after you install. In Claude Code, a SessionStart hook
tells the agent to start the router for each new software task, so you can
also type the task without the command. Codex plugins have no hooks.
[Set up swe](./docs/01-setup.md) gives the lines to put in `AGENTS.md`.

To install only the skills, without the agents or the hook, run
`npx skills@latest add https://github.com/kpeez/agent-toolbox/tree/main/plugins/swe`.

New here? Ask [`/swe:help`](./skills/help/SKILL.md) a question, such as "which
skill reviews a PR?". The [swe guide](./docs/README.md) walks you through a
first real task, from setup and prompts through verification and long runs.

## Usage

Start a task with `/swe:swe-mode`. The router reads your request, picks a
playbook, and runs the other skills as the steps need them.

```text
/swe:swe-mode users get two notifications after a retry. repro first, then fix and verify.
```

```text
/swe:swe-mode i'm stepping away. migrate every caller to the async store, keep behavior identical, and log your decisions.
```

When you start it, the router:

1. Matches your task to a playbook, or to the one skill that owns the task,
   and copies the steps into the task list.
2. Loads each step's skills and principles when that step starts.
3. Applies its rules in every step: triggers, autonomy, and subagent choice.
4. Ends with the result, the evidence, the principles that changed a decision,
   and a Steps section with the state of every step.

When no playbook fits, or the work is large, `figure-it-out` writes a bespoke
playbook in the same format. The full rules are in
[`swe-mode/SKILL.md`](./skills/swe-mode/SKILL.md), and
[Route work](./docs/02-route-work.md) shows the flow as a diagram.

<details>
<summary>The 22 playbooks</summary>

| Playbook | Use for |
| --- | --- |
| [fix-bug](./skills/swe-mode/playbooks/fix-bug.md) | A reported defect to reproduce, root-cause, and fix |
| [improve-performance](./skills/swe-mode/playbooks/improve-performance.md) | A measured slowness, against a baseline |
| [hillclimb-metric](./skills/swe-mode/playbooks/hillclimb-metric.md) | Sustained improvement of one metric, keep or revert per attempt |
| [diagnose-runtime](./skills/swe-mode/playbooks/diagnose-runtime.md) | A live runtime symptom (leak, spin, glitch), diagnosis only |
| [diagnose-trace](./skills/swe-mode/playbooks/diagnose-trace.md) | A captured profile, trace, or heap snapshot, diagnosis only |
| [evaluate-agent-change](./skills/swe-mode/playbooks/evaluate-agent-change.md) | Measure how a skill or prompt change affects agent behavior |
| [author-skill](./skills/swe-mode/playbooks/author-skill.md) | Write or edit a skill, `AGENTS.md`, or `CLAUDE.md` |
| [build-prototype](./skills/swe-mode/playbooks/build-prototype.md) | A throwaway sketch that settles a design fork by observation |
| [match-visual-parity](./skills/swe-mode/playbooks/match-visual-parity.md) | Pixel-exact UI equivalence against a baseline |
| [refactor-structure](./skills/swe-mode/playbooks/refactor-structure.md) | Change structure, keep behavior |
| [build-feature](./skills/swe-mode/playbooks/build-feature.md) | New or changed behavior |
| [investigate-question](./skills/swe-mode/playbooks/investigate-question.md) | A read-only question with a cited answer |
| [babysit-pr](./skills/swe-mode/playbooks/babysit-pr.md) | Drive a PR or stack to merge-ready |
| [ship-stack](./skills/swe-mode/playbooks/ship-stack.md) | Verify a green stack, then land the verified run |
| [run-autonomously](./skills/swe-mode/playbooks/run-autonomously.md) | Drive a long task to a checkable exit condition |
| [plan-multi-phase](./skills/swe-mode/playbooks/plan-multi-phase.md) | Write a plan for work across phases or stacked PRs |
| [autopilot-full](./skills/swe-mode/playbooks/autopilot-full.md) | A queue of independent PRs, run to merged |
| [autopilot-stack](./skills/swe-mode/playbooks/autopilot-stack.md) | A queue of changes, delivered as one stack you land |
| [run-program](./skills/swe-mode/playbooks/run-program.md) | A standing multi-day program under one coordinator |
| [pick-up-session](./skills/swe-mode/playbooks/pick-up-session.md) | Resume a prior agent's in-flight work |
| [pause-safely](./skills/swe-mode/playbooks/pause-safely.md) | Stop in-flight work so a new session can resume it |
| [clean-worktrees](./skills/swe-mode/playbooks/clean-worktrees.md) | Reclaim disk from merged or abandoned worktrees |

</details>

## Skills

The router runs most skills for you when a step needs them. Type one directly
when you want only that job:

```text
/swe:how how do we cancel runs? is there an n+1 when we look up each run?
```

```text
/swe:blast-radius what else could this diff break?
```

<details>
<summary>Skills in the model's skill list</summary>

Each of these also starts on its own when its task comes up.

| Skill | Use it when |
| --- | --- |
| [`interview-user`](./skills/interview-user/SKILL.md) | A plan or design has open decisions only you can make |
| [`handoff`](./skills/handoff/SKILL.md) | You want the work's current state saved for a new session |
| [`log-decisions`](./skills/log-decisions/SKILL.md) | You want an append-only decision log for a long or unattended run |
| [`implement`](./skills/implement/SKILL.md) | You approved a feature or fix and want it built and verified |
| [`diagnose`](./skills/diagnose/SKILL.md) | You want the cause of a bug or a performance regression |
| [`testing-code`](./skills/testing-code/SKILL.md) | You design, gate, or audit tests, or want test-first work |
| [`codebase-design`](./skills/codebase-design/SKILL.md) | You design a new interface, or want deeper module boundaries proposed |
| [`blast-radius`](./skills/blast-radius/SKILL.md) | You want to know what a change could break beyond its diff |
| [`why`](./skills/why/SKILL.md) | You want to know why code or a decision exists |
| [`correct`](./skills/correct/SKILL.md) | Agents keep making the same mistake |
| [`orchestrate`](./skills/orchestrate/SKILL.md) | You want work split across subagents, or sent to another provider |
| [`ship-pr`](./skills/ship-pr/SKILL.md) | You want a commit, a push, and a draft PR driven to green |
| [`verification-skill`](./skills/verification-skill/SKILL.md) | Your project has no scripted way to run and observe the real app |
| [`writing`](./skills/writing/SKILL.md) | You write prose: docs, PR bodies, handoffs, plans, or replies |
| [`writing-for-agents`](./skills/writing-for-agents/SKILL.md) | You write a skill, `AGENTS.md`, or `CLAUDE.md` |
| [`wait-what`](./skills/wait-what/SKILL.md) | You want the last message again in simpler words |

</details>

<details>
<summary>Skills hidden from the model's skill list</summary>

Playbook steps and router triggers read these by path. You can still type
them, such as `/swe:how`.

| Skill | Use it when |
| --- | --- |
| [`help`](./skills/help/SKILL.md) | You want to know which swe skill, playbook, or principle fits |
| [`how`](./skills/how/SKILL.md) | You want a walkthrough of how a subsystem works |
| [`architect`](./skills/architect/SKILL.md) | You want competing designs explored before code |
| [`swarm`](./skills/swarm/SKILL.md) | You want parallel workers: coverage matrices, races, or verifier lanes |
| [`figure-it-out`](./skills/figure-it-out/SKILL.md) | No playbook fits, and you want a bespoke one |
| [`benchmark-checklist`](./skills/benchmark-checklist/SKILL.md) | You measured a number and want it vetted before you report it |
| [`sharpen`](./skills/sharpen/SKILL.md) | You want a vague ask restated as an expert would approach it |
| [`no-comments`](./skills/no-comments/SKILL.md) | You want comments that do not explain a non-obvious why removed |
| [`ketchup`](./skills/ketchup/SKILL.md) | You come back after time away and want to catch up |
| [`recall`](./skills/recall/SKILL.md) | You want recent context rebuilt from chat history and the handoff file |
| [`reflect`](./skills/reflect/SKILL.md) | You want a session reviewed for agent mistakes |
| [`in-your-own-words`](./skills/in-your-own-words/SKILL.md) | You want the agent to restate your goal before it starts |
| [`typescript-best-practices`](./skills/typescript-best-practices/SKILL.md) | You read or edit TypeScript |

</details>

## Agents

The chat that runs `/swe:swe-mode` owns the playbook, the task list, and every
subagent. swe ships two agents for delegates:

- [`daedalus`](./agents/daedalus.md) does one bounded task (code,
  tests, docs, or tracker work) under the caller's brief. It publishes nothing
  without explicit authority.
- [`comment-sicko`](./agents/comment-sicko.md) reviews a diff for
  comments to delete. `no-comments` starts it.

Reviews and searches use the host's own subagents with the
[review brief](./references/review-brief.md).

## Principles

The 25 principles are short hidden skills, one rule each. The router lists each
one with the moment it applies, and reads it by path at that step. Name one in
a prompt to steer the agent, as in "fix the root cause, not the symptom".
[Steer with principle names](./docs/08-principles.md) shows how.

<details>
<summary>The 25 principles</summary>

| Principle | Group | Rule |
| --- | --- | --- |
| [laziness-protocol](./skills/principle-laziness-protocol/SKILL.md) | core | Bias toward deletion and the smallest change that solves the problem. |
| [foundational-thinking](./skills/principle-foundational-thinking/SKILL.md) | core | Choose the core types and data structures before logic, so the downstream code becomes obvious. |
| [redesign-from-first-principles](./skills/principle-redesign-from-first-principles/SKILL.md) | core | Redesign as if a new requirement had been there from the start. |
| [attack-the-premise](./skills/principle-attack-the-premise/SKILL.md) | core | When two fixes that share one premise fail the same check, write the premise down and test it. |
| [subtract-before-you-add](./skills/principle-subtract-before-you-add/SKILL.md) | core | Remove dead code and redundant checks first, then build on the simpler base. |
| [minimize-reader-load](./skills/principle-minimize-reader-load/SKILL.md) | core | Count the layers and state a reader must hold, then collapse wrappers. |
| [outcome-oriented-execution](./skills/principle-outcome-oriented-execution/SKILL.md) | core | In a planned migration, converge on the target with no throwaway compatibility code. |
| [experience-first](./skills/principle-experience-first/SKILL.md) | core | Choose the user's experience over implementation convenience. |
| [exhaust-the-design-space](./skills/principle-exhaust-the-design-space/SKILL.md) | core | With no precedent, build two or three competing prototypes and compare them. |
| [build-the-lever](./skills/principle-build-the-lever/SKILL.md) | core | Build the script, codemod, or generator that does or proves the work. |
| [model-the-domain](./skills/principle-model-the-domain/SKILL.md) | architecture | Encode the domain in a data structure instead of scattered conditionals. |
| [boundary-discipline](./skills/principle-boundary-discipline/SKILL.md) | architecture | Guard at system boundaries, trust internal types, keep business logic pure. |
| [type-system-discipline](./skills/principle-type-system-discipline/SKILL.md) | architecture | Make the compiler reject impossible states and unhandled variants. |
| [make-operations-idempotent](./skills/principle-make-operations-idempotent/SKILL.md) | architecture | Make every rerun reach the same end state. |
| [migrate-callers-then-delete-legacy-apis](./skills/principle-migrate-callers-then-delete-legacy-apis/SKILL.md) | architecture | Migrate every caller and delete the old API in the same change. |
| [separate-before-serializing-shared-state](./skills/principle-separate-before-serializing-shared-state/SKILL.md) | architecture | Remove shared writes before you add a lock. |
| [prove-it-works](./skills/principle-prove-it-works/SKILL.md) | verification | Check the real artifact and give a VERIFIED, NOT VERIFIED, or INCONCLUSIVE verdict. |
| [fix-root-causes](./skills/principle-fix-root-causes/SKILL.md) | verification | Trace each symptom to the first place the system went wrong and fix it there. |
| [sequence-verifiable-units](./skills/principle-sequence-verifiable-units/SKILL.md) | verification | Split work into small units and check each before the next. |
| [test-behavior-not-implementation](./skills/principle-test-behavior-not-implementation/SKILL.md) | verification | Assert what users observe, so the test fails when behavior breaks and passes when internals change. |
| [explain-the-number](./skills/principle-explain-the-number/SKILL.md) | verification | Find what limits a measured number before you trust or report it. |
| [guard-the-context-window](./skills/principle-guard-the-context-window/SKILL.md) | delegation | Send bulk work to subagents and keep summaries in the main thread. |
| [never-block-on-the-human](./skills/principle-never-block-on-the-human/SKILL.md) | delegation | Do reversible work, show the result, and let the human correct it. |
| [encode-lessons-in-structure](./skills/principle-encode-lessons-in-structure/SKILL.md) | meta | Encode a repeated rule as a lint, flag, check, or script. |
| [ancillary-fixes](./skills/principle-ancillary-fixes/SKILL.md) | meta | For an issue outside the task, decide to fix it now or report it. |

</details>
