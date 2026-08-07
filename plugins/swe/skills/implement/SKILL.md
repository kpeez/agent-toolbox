---
name: implement
description: "How to implement a spec or feature: prove behavior before committing to it, and orchestrate the work rather than doing it all yourself. Use whenever implementing a feature, bugfix, or behavior change."
---

# Implement

One verification discipline, two audiences: the orchestrator that fans work
out across tasks, and the implementer that does one. If you're an implementer
node, read "Prove behavior" and "Implement one task" and stop there — the
"Orchestrate the fan-out" section in between is not yours to run.

## Prove behavior before you commit to it

**`/tdd`** is the discipline (the sketch→graduate→settle loop lives there):
goals are covered by evidence, not one test each. Silent failures earn a
committed test at caller altitude, written directly when the behavior is known
or graduated from a `tests/temp/` scratch script when it isn't; several goals
running through one end-to-end path share that pipeline-level test; a goal
whose failure is loud on the first real run is proven by the reproducible demo
`/ship-pr` already requires in the PR. A verdict-only script ends in a recorded
decision — an ADR, spec decision, or tracker entry — rather than a test. If you
catch yourself calling a goal done with nothing that verifies it, STOP and
produce the evidence; a red test, type error, or lint failure is a stop, not a
warning.

## Orchestrate the fan-out

**Owned by the `swe-loop.js` workflow script** whenever one is running —
the frontier loop, model selection, and status handling below execute as the
script's deterministic logic. Outside a workflow run — interactive
sessions, one-off fixes — you are the orchestrator and follow this section by
hand. Either way, an implementer never runs this section on its own task.

### Working from the tracker

Take the next unblocked workable issue. Tasks in an approved spec's container
are **ready by construction** — work any unblocked one without interrogating
labels; skip only `ready-for-human`. The `ready-for-agent` label matters when
picking up issues from other sources (the triage vocabulary and tracker
selection live in `/to-issues`).

### Don't do it all yourself

Unless the change is highly trivial, **don't explore the codebase or write the
code yourself — delegate.** Spend your context coordinating, not reading files
and typing implementation.

- **Explore** with an explorer-tier worker (the `Explore` or
  `swe:explorer` subagent) instead of loading many files into your own
  context.
- **Generate** with a `swe:implementer`. Give it exactly
  the context it needs — the relevant
  `NNNN-<slug>.md` sections, key paths, and where the task fits — no more.
- **Review** what comes back before trusting it.

**The fan-out loop:** take the next unblocked issue → spawn an **implementer**
(the `swe:implementer` agent) with the issue, a pointer to the spec, and its
own `/goal` → review the diff → update the tracker → repeat.

### Sequential or parallel?

- Tasks share files or have ordering dependencies → **sequential**.
- Tasks are independent (disjoint files, no shared state) → **parallel**.

When uncertain, sequential. Parallel conflicts are harder to recover from than
sequential slowness.

### Model selection

Each role pins the least powerful default that still covers its full contract:

| Role        | Claude        | Codex                    | Why                                                   |
| ----------- | ------------- | ------------------------ | ----------------------------------------------------- |
| explorer    | haiku         | luna, medium             | Bounded read-only lookup and evidence gathering       |
| architect   | fable, high   | sol, high                | Open-ended design resolution and specification        |
| planner     | sonnet, medium | terra, medium           | Constrained decomposition of an approved design       |
| implementer | sonnet, medium | sol, medium             | Well-specified code changes; the spec, task bounds, and review pass carry the quality bar |
| reviewer    | sonnet, high  | terra, high              | Narrow but correctness-sensitive checking             |
| publisher   | sonnet, medium | terra, medium           | Procedural release work with commit-boundary judgment |

A role routed to another provider (`codex`, `copilot`) does not use this
matrix: it runs through that provider's forwarder agent on the provider's own
default model, unless the dispatching prompt names one.

Claude Haiku does not support the per-agent `effort` setting, so the explorer
intentionally specifies only its model. The architect's `fable` pin degrades
gracefully — where Fable 5 is unavailable, the subagent falls back to the
session's inherited model rather than failing. Keep these role defaults in the
provider agent definitions; do not spend frontier-model tokens on a bounded
role by default.

Always tell the worker to follow the verification discipline — cover each
stated goal with evidence per `/tdd`, run and passing — and to report
status (DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED). Handle each status
before proceeding: address concerns that touch correctness or scope, provide
missing context and re-dispatch, or diagnose a block before retrying.

### After each task

Update the tracker issue: move it to Done, or comment progress using the
residue checklist from "Implement one task" step 4. Status and tasks live on
the tracker, not in a local file.

### Escalation ladder

A blocked worker reports up, never out — BLOCKED/NEEDS_CONTEXT to whoever
orchestrates it (the conductor, or you in an interactive session), never a
prompt to the user. Resolve what the spec, ADRs, or codebase answer; log the
decision on the issue; relaunch. Interrupt the user only for a scope change, a
spec contradiction, a blocking `ready-for-human` task, or a
destructive/irreversible action.

## Implement one task

The discipline an **implementer** agent — or you, working a single issue
directly — follows for ONE task, handed to it as identifiers only (spec path,
slug, container id, issue id). Never delegate this task further and never run
the fan-out above; that's the orchestrator's job.

1. Read the issue body (the brief) and its latest comment (the handoff) before
   acting.
2. Prove behavior per `/tdd` — tdd-first, sketching in `tests/temp/` when the
   design is uncertain.
3. Verification gates, in order: lint → types → tests. A failure at any gate
   stops the task; it is not a warning to note and continue past.
4. Comment tracker progress on the issue before you finish or run out of
   context. Don't re-narrate what artifacts already record (the diff, the spec,
   issue state) — write only the residue the session holds, a line or two per
   non-empty category, leading with Resume:
   - **Resume** — the concrete next action: the command to run, the step to take
   - **Ruled out** — approaches tried and abandoned, and why
   - **Gotcha** — non-obvious constraints discovered the hard way
   - **Correction** — where the spec or issue body is now stale, and what's true
   - **In flight** — work started but not committed, and its state

   This comment is your required output, not optional bookkeeping — the next
   agent reads it as the handoff.
5. Report status to whoever orchestrates you — DONE / DONE_WITH_CONCERNS /
   NEEDS_CONTEXT / BLOCKED. If mid-task you hit a decision only a human can
   make: in a workflow run, comment exactly what's needed and report
   NEEDS_CONTEXT or BLOCKED — your orchestrator escalates it (relabeling
   `ready-for-human` if warranted); never prompt the user directly. In an
   interactive session the user is your orchestrator — ask them, same as
   `/tdd`'s interactive branch.

## Cross-references

- `/sharpen` — stress-test a plan before writing tests or scratch scripts.
- `/write-spec new <name>` — scaffold a pure-markdown spec whose Verification section names the tests.
