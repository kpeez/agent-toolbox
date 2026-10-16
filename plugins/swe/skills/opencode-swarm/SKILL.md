---
name: opencode-swarm
description: "Fan out a small swarm of OpenCode workers on free OpenCode Zen models, then verify and merge their results. Use when the user asks for OpenCode Zen, free models, or an OpenCode swarm."
argument-hint: "<task>"
disable-model-invocation: true
---

# OpenCode swarm

The lead is this Claude session. It splits the work, writes each worker's
brief, runs the swarm through
[opencode_swarm.py](../../scripts/opencode_swarm.py), and owns every result.
[orchestrate](../orchestrate/SKILL.md) owns the brief fields and the
external-provider rules. [swarm](../swarm/SKILL.md) owns the shapes and the
single report. This skill adds the OpenCode Zen route. `<plugin-root>` is two
folders above this skill's directory.

A free Zen model is a third party that can keep the prompt. Send it only the
repository content the user authorized for OpenCode. Free models are weaker
than the lead: treat every worker answer as a lead to check, not a finding.

## Steps

1. **Check OpenCode.** Run `opencode --version`. The script supports
   OpenCode 2.x (npm `@opencode/cli`) and 1.x (npm `opencode-ai`). The free
   models need no login.
2. **List the free models.** Run
   `python3 <plugin-root>/scripts/opencode_swarm.py models`. It prints the
   `opencode/` models with zero cost that can call tools. The list changes
   often, so never hard-code a model ID.
3. **Frame the swarm.** Pick a swarm shape: a coverage matrix for one slice
   per worker, or a race for one brief on several models. Keep three to five
   workers. Each worker gets one bounded question that it can answer by
   reading files.
4. **Write the task file.** A JSON list of
   `{"id": "<slug>", "prompt": "<brief>"}` objects, with optional `model`,
   `dir`, and `files`. A worker sees no chat, so each prompt names the goal,
   the absolute paths to read, and the report format, such as one
   `path:line: finding` per line or `NONE`.
5. **Run it.** Run
   `python3 <plugin-root>/scripts/opencode_swarm.py run tasks.json --dir <repo>`.
   Workers are read-only by default and get models from the free list in
   turn. A failed task runs once more on the next model. Add `--out <dir>` to
   keep raw event streams. Run `run --help` for the other flags. Some free
   models are slow, so a worker can take several minutes.
6. **Verify.** Read the JSON line of each task. Check each claim in the code
   before you use it. Drop claims you cannot confirm. For a race, apply the
   selection rule you declared in step 3. A task with status `error` or
   `timeout` is a gap, not a pass.
7. **Report.** Give one report per [swarm](../swarm/SKILL.md#phase-d-report):
   the verified results, the model of each worker, and the gaps.

## Edits

Use `--edit` only when a worker must write files. Every task then needs its
own `dir`, such as a git worktree from `git worktree add`. The script allows
read and edit tools and denies shell, web, code mode, and nested subagents in
both modes. This is OpenCode's permission config, not an OS sandbox. Review each
worktree's diff as you would a stranger's patch before you take any of it.
