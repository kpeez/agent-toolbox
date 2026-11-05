# Antigravity

The Antigravity CLI is `agy`. It runs Gemini models, and on some accounts also
Claude and GPT-OSS models. Upstream docs:
[headless mode](https://antigravity.google/docs/cli/headless/),
[CLI reference](https://antigravity.google/docs/cli/reference/), and
[permissions](https://antigravity.google/docs/permissions?tab=cli).

## Check

Run `agy --version`. The skill was tested on agy 1.5.1. `agy --help`
prints to stderr. A headless run uses the cached sign-in, so the user signs
in once in an interactive `agy` session first. Without a sign-in, a headless
run prints an OAuth URL, waits 60 seconds, and exits 1. For CI, the docs offer
a Gemini API key (`modelProvider: "gemini"` in settings and `GEMINI_API_KEY`)
or Application Default Credentials (`AGY_ADC_AUTH=true`).

## Models and effort

`agy models` prints one tab-separated slug and name per line. Each slug
carries its effort level, such as `gemini-3.8-flash-high`. An unknown slug
fails the run; agy does not fall back to another model.

- **The user named models.** Pass `--model <slug>`. For a worker's effort,
  pick the slug of the same model with the nearest level, the higher one on
  a tie. Give workers different models in turn.
- **No model named.** Leave out `--model`; agy uses the model in the user's
  agy settings. Pass `--effort <level>` instead, one of `low`, `medium`,
  `high`, `xhigh`, or `max`. Use `low` for `none` and `minimal`.

## Run a worker

Each worker runs in agy's OS sandbox. First write its settings file,
`<run>/<id>.agy.json`. Use the real paths from the skill's run-folder rule:
agy matches a rule against the real path, so a rule on a linked path is
denied. On macOS, `$TMPDIR` is under `/var`, a link to `/private/var`.

```json
{
  "toolPermission": "proceed-in-sandbox",
  "permissions": {
    "allow": ["read_file(<run>)", "write_file(<worktree>)"]
  }
}
```

The same command serves a questions worker and a delegate. Run it from your
worktree as one plain command, with no `cd` or `env` in front, so that a
narrow permission rule for `agy` can match it (see
[host-permissions.md](host-permissions.md)). Put either `--model <slug>` or
`--effort <level>` where the command shows `<model or effort>`.

```sh
agy --print="Read <run>/<id>.md and follow it. End with your answer as plain text." --sandbox --settings <run>/<id>.agy.json --add-dir <run> <model or effort> --output-format json --print-timeout <seconds>s --disable-slash-commands < /dev/null > <run>/<id>.json 2> <run>/<id>.log
```

- `--sandbox` with `proceed-in-sandbox` runs every shell command inside the
  OS sandbox with no prompt: Seatbelt on macOS, kernel namespaces on Linux.
  Tested on agy 1.5.1: a command could write in the worktree, could not
  write outside it, and had no network.
- The file tools may read the workspace by default. The allow rules add the
  run folder, for the brief, and writes in the worktree. Headless mode
  denies any other read or write, because it cannot ask. `--add-dir` alone
  does not allow the brief to be read.
- The network is off for commands. When a delegate must install packages or
  fetch dependencies, add `read_url(<domain>)` to `allow` for each domain it
  needs; agy adds those domains to the sandbox's outbound allowlist.
- A delegate's build can fail on a cache outside the worktree, such as
  `~/.cache`, `~/.npm`, or `~/.cargo`. Add a `write_file(<path>)` rule for
  each cache the spec's build needs. `git commit` also fails, because the
  shared `.git` is outside the worktree; the brief already says not to
  commit.
- Never add `--dangerously-skip-permissions`. It also approves the
  requests to bypass the sandbox, so the worker can run outside the sandbox
  ([agy issue #36](https://github.com/google-antigravity/antigravity-cli/issues/36)).
- Use `--print-timeout 600s` for a questions worker and `3600s` for a
  delegate.
  Always pass it: in agy 1.4.12 and later it waits forever by default (`0s`).
- `--disable-slash-commands` keeps a `/` in the brief from running a slash
  command or skill.

The sandbox covers shell commands. The file tools follow the allow rules
above. Whether a sandboxed command can read files outside the worktree was
not tested.

## Read the result

`<run>/<id>.json` is one JSON envelope with `conversation_id`, `status`,
`response`, `duration_seconds`, `num_turns`, and `usage`. An error or a
timeout adds `finished_reason`.

Test the cases in this order:

1. `timeout`: `finished_reason` is `print_timeout`. agy still exits 0 with
   status `SUCCESS`, and `response` can hold a partial answer.
2. `ok`: exit 0, `status` is `SUCCESS`, no `finished_reason`, and
   `response` is not empty.
3. `error`: any other result, such as an empty `response`, a
   `denied_actions` list, or exit 1 for a failed sign-in or an unknown
   model. The end of `<run>/<id>.log` says why.

## Other headless features

- `--settings <json or file>` applies settings for one run and never saves
  them, such as `{"permissions": {"deny": ["read_url(*)"]}}`. Deny rules beat
  ask and allow rules.
- `--json-schema <schema or file>` makes `structured_output` hold the parsed
  answer.
- `--output-format stream-json` prints NDJSON events: `init`, `step_update`
  (with `tool_name` and `tool_info` on tool steps), and `result`. Use it to
  watch a long delegate run.
- `--continue` or `--conversation <id>` resumes a conversation in a new
  process, such as a second delegate round.
- The user's global rules (`~/.gemini/config/AGENTS.md`) still load in a
  headless run.
