# Antigravity

Script: [agy_run.py](../scripts/agy_run.py). Its docstring and `--help` hold
every flag.

The Antigravity CLI is `agy`. It runs Gemini models, and on some accounts also
Claude and GPT-OSS models. Upstream docs:
[headless mode](https://antigravity.google/docs/cli/headless/),
[CLI reference](https://antigravity.google/docs/cli/reference/), and
[permissions](https://antigravity.google/docs/permissions?tab=cli).

## Check

Run `agy --version`. The script was tested on agy 1.4.12. `agy --help`
prints to stderr. A headless run uses the cached sign-in, so the user signs
in once in an interactive `agy` session first. Without a sign-in, a headless
run prints an OAuth URL, waits 60 seconds, and exits 1. For CI, the docs offer
a Gemini API key (`modelProvider: "gemini"` in settings and `GEMINI_API_KEY`)
or Application Default Credentials (`AGY_ADC_AUTH=true`).

## Models

Run `agy_run.py models`. Each slug carries its effort level, such as
`gemini-3.8-flash-high`. `run --models <a,b>` rotates tasks over those slugs,
and a failed task runs once more on the next slug. Without `--models`, every
task uses the model in the user's agy settings. A task's `effort` picks the
slug of the same model with the nearest level. An unknown slug fails the
task; agy does not fall back to another model.

## Headless behavior

The script runs `agy --print=<prompt> --output-format json`. The JSON
envelope has `conversation_id`, `status`, `response`, `duration_seconds`,
`num_turns`, and `usage`. A denied tool adds `denied_actions`, and an error or
timeout adds `finished_reason`.

agy exits 0 with status `SUCCESS` in three cases that are not a pass:

- A tool needed approval. Headless mode cannot ask, so it denies the tool and
  often ends with an empty `response`.
- `--print-timeout` ran out. `finished_reason` is `print_timeout`.
- The model ended with no text.

The script reports the first and third as `error` and the second as
`timeout`. Exit 1 means a hard error, such as a failed sign-in or an unknown
model.

`--print-timeout` waits forever by default in agy 1.4.12 (`0s`); the headless
docs say five minutes. The script always passes its own `--timeout`.

## Permissions

With the default `request-review` preset, a headless run may read files in
the workspace and denies writes and shell commands. The user's
`~/.gemini/antigravity-cli/settings.json` can loosen that, so the script
passes `--settings` with deny rules for `write_file(*)`, `command(*)`,
`read_url(*)`, `execute_url(*)`, and `mcp(*)`. `--settings` applies to one run
and is never saved. Deny rules beat ask and allow rules. A deny-rule hit does
not appear in `denied_actions`; the model sees the error and answers around
it.

No permission rule stops the `search_web` tool: runs with `read_url(*)` and
`search_web(*)` denied still searched the web. The prompt note is the only
guard, so send no secret in a prompt that a search query could leak.

`--edit` drops the `write_file` deny, allows writes in the task's `dir`, and
adds `--mode accept-edits`. Commands, URL reads, browser actions, and MCP
stay denied. This is agy's
permission engine, not an OS sandbox. `--sandbox` adds OS containment for
shell commands, which the script never allows.

The user's global rules (`~/.gemini/config/AGENTS.md`) still load. A rule that
tells the model to use a shell tool makes it try a command, which headless
mode denies, and the answer can come back empty. The script adds a read-only
note to each prompt so the model stays on read and search tools. A worker
that refuses a write in plain text still has status `ok`, so read its text.

## Other headless features

- `--json-schema <schema or file>` makes `structured_output` hold the parsed
  answer.
- `--output-format stream-json` prints NDJSON events: `init`, `step_update`
  (with `tool_name` and `tool_info` on tool steps), and `result`.
- `--continue` or `--conversation <id>` resumes a conversation in a new
  process. `--input-format stream-json` with `--output-format stream-json`
  keeps one process for many turns; write
  `{"event":"user","message":{"content":"..."}}` lines to stdin and close
  stdin to end it.
- Parallel runs in one directory work. Each run gets its own conversation.
- Result lines print in completion order, not task order.
