---
name: opencode
description: "Fan out a small swarm of OpenCode workers on any model OpenCode can reach (Zen, Go, Copilot, and others), then verify and merge their results. Use when the user asks for OpenCode workers or an OpenCode swarm."
argument-hint: "<task>"
disable-model-invocation: true
---

# OpenCode

The lead is this Claude session. It splits the work, writes each worker's
brief, runs the workers through
[opencode_run.py](../../scripts/opencode_run.py), and owns every result.
[orchestrate](../orchestrate/SKILL.md) owns the brief fields and the
external-provider rules. [swarm](../swarm/SKILL.md) owns the shapes and the
single report. `<plugin-root>` is two folders above this skill's directory.

OpenCode reaches models through the providers the user connected: OpenCode
Zen, OpenCode Go, GitHub Copilot, and others. Every provider takes the same
path below. A provider is a third party, and free models can keep the prompt.
Send only the repository content the user authorized for OpenCode. Treat
every worker answer as a lead to check, not a finding.

## Steps

1. **Check OpenCode.** Run `opencode --version`. The script supports
   OpenCode 2.x (npm `@opencode/cli`) and 1.x (npm `opencode-ai`).
2. **Choose the pool.** Run `python3 <plugin-root>/scripts/opencode_run.py prefs`.
   A saved `models` list is the user's pool. With no saved list, the pool is
   every free model. Run `models` to see each model OpenCode can reach, with
   its provider and whether it is free. When the user names models or a
   provider, save that choice with `prefs --models <a,b>`. Use a paid model
   only when the user named it.
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
   `python3 <plugin-root>/scripts/opencode_run.py run tasks.json --dir <repo>`.
   Workers are read-only by default and take models from the pool in turn.
   A failed task runs once more on the next model. `--models` overrides the
   pool for one run. Add `--out <dir>` to keep raw event streams. Run
   `run --help` for the other flags. Some models are slow, so a worker can
   take several minutes.
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
both modes. This is OpenCode's permission config, not an OS sandbox. Review
each worktree's diff as you would a stranger's patch before you take any of
it.
