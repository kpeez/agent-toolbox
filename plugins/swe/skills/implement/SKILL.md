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
and typing implementation. The delegation surface depends on what the host
offers:

- **On a host with named subagents**, explore with `swe:opencode-explorer`,
  give one bounded changeset to `swe:opencode-implementer`, and send the final
  assembled diff to `swe:opencode-reviewer`. Those thin forwarders make the
  typed OpenCode calls.
- **On a host without them**, call the plugin-delivered tools directly. Every
  call names the absolute worktree root as `cwd`: use
  `mcp__plugin_swe_opencode-explorer__delegate` with `mode: "read-only"` for
  repository archaeology,
  `mcp__plugin_swe_opencode-implementer__delegate` with `mode: "write"` for
  exactly one changeset and its issue/spec identifiers and evidence gates, and
  `mcp__plugin_swe_opencode-reviewer__delegate` with `mode: "read-only"` for
  one review of the complete assembled diff.

The model is pinned by the plugin and is not a delegation argument. If a
requested OpenCode tool is missing, fails to start, or returns non-completion,
surface that result to the orchestrator. There is no silent fallback to a
host-native agent and no `opencode run` shell-out path. A user may explicitly
choose a host-native role where the calling workflow supports provider routing;
that explicit choice is not a fallback.

**The fan-out loop:** take the next unblocked changeset → send its bounded task
to the host-specific OpenCode implementer above with its own `/goal` → inspect
the result and update the tracker → repeat. When the frontier drains, send the
assembled change to the host-specific OpenCode reviewer once before publishing.

### Sequential or parallel?

- Tasks share files or have ordering dependencies → **sequential**.
- Tasks are independent (disjoint files, no shared state) → **parallel**.

When uncertain, sequential. Parallel conflicts are harder to recover from than
sequential slowness.

### Model selection

Each role pins the least powerful model that still covers its full contract:
cheap for bounded read-only lookup (explorer); mid-tier for constrained
decomposition, well-specified code changes, and procedural release work
(planner, implementer, publisher — the spec, task bounds, and review pass
carry the quality bar); stronger reasoning only where the work is open-ended
or correctness-sensitive (architect, reviewer).

The pins themselves live in the provider agent definitions and the plugin's
MCP companion configs, never in a skill or a dispatching prompt. A role routed
to OpenCode is pinned to its model at the MCP layer and accepts no model
argument. Do not spend frontier-model tokens on a bounded role by default.

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
