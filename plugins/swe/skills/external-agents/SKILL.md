---
name: external-agents
description: "Run one-shot workers on another agent CLI, such as OpenCode (Zen, Go, Copilot models) or Antigravity `agy` (Gemini models), then verify their results. Use when the user asks for OpenCode, Antigravity, agy, or Gemini workers, a swarm on one of them, or a second opinion from one."
argument-hint: "<task>"
---

# External agents

The lead is this session. It splits the work, writes each worker's brief,
runs the workers through the harness script, and owns every result.
[swarm](../swarm/SKILL.md) owns the shapes, the brief fields, and the single
report. `<skill-dir>` is this skill's directory.

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

## Steps

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

## Edits

Use `--edit` only when a worker must write files. Every task then needs its
own `dir`, such as a git worktree from `git worktree add`. The reference says
what the harness allows in each mode. Review each worktree's diff as you
would a stranger's patch before you take any of it.
