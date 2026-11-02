---
name: external-agents
description: "Run workers on another agent CLI, such as OpenCode (Zen, Go, Copilot models) or Antigravity `agy` (Gemini models): a swarm of small read-only questions, or a whole spec delegated for implementation that Claude then reviews and fixes. Use when the user asks for OpenCode, Antigravity, agy, or Gemini workers, a swarm or second opinion on one, or to hand one a spec to build."
argument-hint: "<task>"
---

# External agents

The lead is this session. It writes each worker's brief, runs the workers
through the harness script, and owns every result. `<skill-dir>` is this
skill's directory.

The skill has two modes:

- **Swarm**: three to five workers, each with one bounded read-only question.
  The lead checks every claim.
- **Delegate**: one worker builds a whole spec in its own worktree. The lead
  then reviews the work against the spec and finishes it.

## Harnesses

| Harness | Models | Reference | Script |
| --- | --- | --- | --- |
| OpenCode | Zen, Go, Copilot, and any other provider the user connected | [opencode.md](references/opencode.md) | `scripts/opencode_run.py` |
| Antigravity (`agy`) | Gemini, and Claude or GPT-OSS on some accounts | [antigravity.md](references/antigravity.md) | `scripts/agy_run.py` |

Use the harness the user named. With no harness named, use OpenCode. Read the
harness reference before step 1.

A provider is a third party, and free models can keep the prompt. Send only
the repository content the user authorized for that provider. Treat every
worker answer as a lead to check, not a finding.

## Task file

Every script takes the same task file: a JSON list of
`{"id": "<slug>", "prompt": "<brief>"}` objects, with optional `model`,
`effort` (`none` to `max`), `dir`, and `files`. Every script prints one JSON
line per task with `id`, `model`, `effort`, `status` (`ok`, `error`, or
`timeout`), `exit`, `seconds`, `attempts`, `text` (the final answer), `error`,
and `session`. [workers.py](scripts/workers.py) holds this contract.

## Swarm

1. **Check the harness.** Run the version check in the reference.
2. **Choose models.** Follow the reference. Use a paid model only when the
   user named it.
3. **Frame the swarm.** Pick a swarm shape: a coverage matrix for one slice
   per worker, or a race for one brief on several models. Keep three to five
   workers. Each worker gets one bounded question that it can answer by
   reading files.
4. **Write the task file.** Set `effort` per task as you would for a native
   subagent: `low` for mechanical lookups, `medium` for routine reading,
   `high` or above for judgment. A worker sees no chat, so each prompt names
   the goal, the absolute paths to read, and the report format, such as one
   `path:line: finding` per line or `NONE`.
5. **Run it.** Run
   `python3 <skill-dir>/scripts/<script> run tasks.json --dir <repo>`.
   Workers are read-only by default. Run `run --help` for the other flags.
6. **Verify.** Read the JSON line of each task. Check each claim in the code
   before you use it. Drop claims you cannot confirm. For a race, apply the
   selection rule you declared in step 3. A task with status `error` or
   `timeout` is a gap, not a pass.
7. **Report.** Give one report per [swarm](../swarm/SKILL.md#phase-d-report):
   the verified results, the harness and model of each worker, and the gaps.
   [swarm](../swarm/SKILL.md) owns the shapes and the brief fields.

Use `--edit` only when a swarm worker must write files. Every task then needs
its own `dir`, such as a git worktree from `git worktree add`. The reference
says what the harness allows.

## Delegate

1. **Check the harness and choose the model** as in the swarm steps. Pick a
   strong model at `high` effort or above.
2. **Fix the spec.** The spec is a file the worker can read. It names each
   requirement, the files in scope, and the commands that build and test the
   work. Number the requirements, such as `R1-csv-bom`. A spec with an open
   product decision goes back to the user first.
3. **Make the worktree.** Run
   `git worktree add -b <branch> <path> <base>`. The worker gets this path as
   its `dir`, and nothing else.
4. **Run the worker.** Run the delegate command in the harness reference,
   in the worktree. It calls the CLI directly with its own permission
   bypass, because a denied tool ends a headless run early. The worker can
   then run any command and reach the network. The prompt points to the
   spec, says to build and test every requirement, and asks for a final list
   of each requirement with `done` or `not done`.
5. **Review against the spec.** Read the whole diff in the worktree. Mark
   each requirement met, partly met, or missing, with `path:line` evidence.
   Look for changes outside the spec's scope. The worker's own list is a
   claim, not evidence.
6. **Run the checks yourself.** Run the spec's build and test commands in the
   worktree. A check the worker says passed counts only when your run passes.
7. **Finish the work.** Fix each gap and failure yourself in the worktree.
   When the gaps are large, send one more worker round with the open
   requirements and your findings, then go back to step 5.
8. **Report.** Give the requirement table, the changes you made after the
   worker, the check results, and the branch. Publish the branch per
   [ship-pr](../ship-pr/SKILL.md).
