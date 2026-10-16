---
name: swarm
description: "Fan out N parallel workers, drain them, and return one report. Use for parallel coverage matrices, races, gauntlets, exploration partitions, and verifier lanes."
argument-hint: "<task>"
disable-model-invocation: true
---

# Swarm

Swarm owns the fan-out shape. [orchestrate](../orchestrate/SKILL.md) owns the
delegation contract. Apply its delegation preflight and brief fields to every
worker. Use its external-provider mode when a worker runs on a provider the
user named.

## Shapes

- **Coverage matrix**. Partition the work into slices, such as one per
  platform, package, or test target. Every slice needs a result.
- **Race**. N workers get identical briefs, or one brief on different models.
  A selection rule picks the result.
- **Gauntlet**. Several independent checkers attack one artifact from
  different angles. Every lane reports.
- **Exploration partition**. Split an open question into distinct angles, one
  worker per angle, as the [how](../how/SKILL.md) explorers do.
- **Verifier lanes**. Each lane verifies or measures named commits with a
  named method. The brief names the exact SHAs.

## Start

Open the host's task list with one entry per phase before you launch anything.

1. Frame
2. Fan out
3. Aggregate
4. Report

## Phase A: Frame

1. State the done predicate and the artifact or report the swarm must return.
2. Choose the shape. Partition into slices, race N workers on identical
   briefs, or mix both. For a race or a mixed shape, declare `first pass`,
   `rank all`, or `best-of` before you spawn.
3. Pick the worker model by role. In Claude Code, use `sonnet` for routine
   workers, `haiku` for mechanical lanes, and `opus` for judgment or the
   hardest code. In Codex, set reasoning effort the same way. For a model
   race, name each arm's model up front. A diversity arm can run on a
   different Claude model, or on an external provider through orchestrate. If
   the host rejects a model, use the host default and say so.
4. Give each worker its own writable output when it writes. Use a worktree
   per worker or disjoint paths. When workers verify or measure commits, each
   brief names the exact SHAs. A measurement brief also names the method,
   which is the sample count, what one sample is, and the order. The worker records both in its
   result.

## Phase B: Fan out

**Workflow path, Claude Code only.** Run Phases B and C as one Workflow
script when the host lists the Workflow tool and the user opted in. Opt-in
means the user typed `/swe:swarm`, asked for a workflow in their own words,
or turned on ultracode. A router that read this file by path is not opt-in.
Load `workflow-authoring` first. In the script, run `pipeline()` over the
slices or race arms, with one `agent()` per worker. Give each worker a
`schema` for its `PASS`, `ISSUES`, or `BLOCKED` report. A worker that writes
code gets `agentType: "swe:daedalus"` and `isolation: "worktree"`. `log()`
each lane the script drops. Apply the Phase C rules to the returned results.
In every other case, and in Codex, use the Agent path below.

**Agent path.** Spawn all N workers in one message, in the background. In Claude Code, use
the Agent tool with `run_in_background: true`. Use `swe:daedalus` for workers
that change code, and a native subagent for search or review. Give a writing
worker `isolation: "worktree"`. When the user has cloud sessions, a Claude Code
cloud session can run a worker instead. In Codex, use subagents or cloud
tasks. Run a worker locally only when it needs something on the user's
computer.

When a worker must start from a non-default branch, push that branch and
name it in the brief. The worker creates its worktree from it.

Every brief stands alone. Include the goal, scope, exact slice or race arm,
how to verify, and what to report. Reports use `PASS`, `ISSUES`, or `BLOCKED`
with evidence. A worker that can prove a defect reports `ISSUES` and lists
every issue it can prove, not only the first.

If a worker drops out, proceed with N-1 and note it.

## Phase C: Aggregate

Read the terminal results. Drop a result that does not record the SHAs and
method its brief names, and respawn that worker once. After a second miss,
record a gap. A gap does not count as a pass. For coverage, every required
slice needs a result. For a race, apply the selection rule declared up front.
Use first pass, rank all, or best-of. Do not paste raw worker dumps.

## Phase D: Report

Return one consolidated in-chat report with the table, the issue one-liners,
gaps or dropouts, and the race rule when used.
