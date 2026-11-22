---
name: verify-swe-hooks
description: Start real headless Claude Code sessions with the swe plugin from this checkout, fire each swe hook, and assert on what the hook did. Use when a change touches plugins/swe/hooks/, plugins/swe/scripts/, or plugins/swe/skills/ship-pr/scripts/pr_body.ts, or when you add a swe hook.
paths:
  - plugins/swe/hooks/**
  - plugins/swe/scripts/**
  - plugins/swe/skills/ship-pr/scripts/pr_body.ts
---

# Verify the swe hooks

The surface is the swe plugin hooks in `plugins/swe/hooks/hooks.json`. The
check runs `claude -p` with `--plugin-dir plugins/swe` of this checkout, so
the hooks under test are the checkout's hooks, not the installed ones.

## Launch

From the repository root:

```sh
uv run .agents/skills/verify-swe-hooks/scripts/check.py
```

Needs uv, `claude`, and a signed-in Claude Code (`CLAUDE_CONFIG_DIR` passes
through from your environment). It runs one session per feature, all in
parallel, and takes under 15 seconds.

Options:

- `--model <name>`: pass a model to `claude --model`. Default: your default.
- `--keep`: keep the throwaway repos and streams for reading.
- `<feature> ...`: run only the named features.

It prints `PASS <feature>` or `FAIL <feature>: <observed>` for each feature.
It exits 0 only when all pass. It starts no server, so Launch needs no
teardown beyond Cleanup.

## Doctor

Read-only. Run before a drive, and again when a result looks wrong:

```sh
claude --version
uv run .agents/skills/verify-swe-hooks/scripts/check.py --help
```

The check itself fails with `no init event` when `claude` cannot start (not
signed in, no network). It fails with `plugin dir ... not loaded` when the
plugin did not load. Both mean "fix the setup", not "the hook is broken".

## Drive

Each feature is one prompt in `FEATURES` in `scripts/check.py`. The prompt
gives the model the exact command to run. The session uses
`--setting-sources project`, so no installed plugin or user hook adds noise.
Each feature allows only the commands it drives (`allowed_tools`, for
example `Bash(gh pr create:*)`). Hooks fire before the permission check. Any
other command is denied, not prompted, because `-p` cannot ask.

The session runs in a throwaway git repo at
`.agents/scratch/verify-swe-hooks/<feature>/`. Each feature has its own repo,
so parallel sessions do not share state.

## Evidence

The check asserts on facts in the `stream-json` events, never on the model's
words:

- `hook_response` events (`--include-hook-events`): hook name, `exit_code`,
  `stdout`, `stderr`.
- `tool_result` blocks: the text the model received from a blocked tool call.

A feature that sees no event from its hook fails. A silent hook never passes.

Evidence survives in `stream.jsonl` in each repo only with `--keep`. Without
it, the failure line is the evidence.

## Feature map

| Feature | Hook | Prompt runs | Passes when |
| --- | --- | --- | --- |
| `session-start` | `SessionStart` | a one-word reply | the hook exits 0 and its stdout equals `hooks/session-start.md` |
| `pr-body-blocks-bad` | `PreToolUse` on `Bash` | `gh pr create` with a body that names a requester | the hook exits 2 with `PR body blocked by ship-pr`, and a `tool_result` carries that text |
| `pr-body-allows-good` | `PreToolUse` on `Bash` | `gh pr create` with a body that fills the template | the hook fires, exits 0, and no `tool_result` carries a block message |
| `gate-session-start` | `SessionStart` | a one-word reply in a repo with a `verify-demo` skill | a hook prints the gate `run` command with the plugin path |
| `gate-blocks-unverified` | `PreToolUse` on `Bash` | edit `src/a.txt`, then `git commit` with `SWE_VERIFY_GATE=enforce` | the hook exits 2 with `Commit blocked by the verify gate`, and a `tool_result` carries it |
| `gate-allows-verified` | `PreToolUse` on `Bash` | edit, run the check through the gate `run` command, then commit | the run prints `verify-demo VERIFIED`, no hook blocks, and the commit lands |
| `gate-blocks-stale` | `PreToolUse` on `Bash` | edit, run through the gate, edit again, then commit | the block message says `verify result is stale: files changed since the run` |
| `gate-allows-outside-paths` | `PreToolUse` on `Bash` | edit `docs/d.md`, outside `src/**`, then commit | no hook blocks and the commit lands |

The gate features run in a throwaway repo with a `verify-demo` skill (`paths: [src/**]`) and `SWE_VERIFY_GATE=enforce`. They edit files with `tee`, because Claude Code asks before a shell redirection writes a file.

`gh pr create` itself may fail in the repo, which has no remote. That is
fine. The feature checks only the hook.

## Add a feature

1. Write a `judge_<name>(events)` function. It returns `None` on pass, or a
   one-line observed fact on failure. Reuse `hook_responses` and
   `tool_results`.
2. Add one `FEATURES["<name>"] = Feature(prompt, judge, files)` entry. Put
   files the prompt needs in `files`. List the narrowest `allowed_tools` the
   command needs, such as `Bash(git commit:*)`. A feature with no tool use
   lists none. Name the exact command in the prompt.
3. Add a row to the feature map above.

Prove each new judge can fail: break the hook on purpose, run the check, see
`FAIL`, and revert the break.

## Cleanup

The check removes `.agents/scratch/verify-swe-hooks/` at the end, also on
error. It starts no other process. After a run you killed, delete that folder.

## Helpers

`scripts/check.py` is the only helper. It is executable, and Launch shows how
to call it.
