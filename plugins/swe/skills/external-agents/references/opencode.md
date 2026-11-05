# OpenCode

OpenCode reaches models through the providers the user connected: OpenCode
Zen, OpenCode Go, GitHub Copilot, OpenAI, local Ollama, and others. Every
provider takes the same command.

## Check

Run `opencode --version`. The skill needs OpenCode 2.x (npm `@opencode/cli`)
and was tested on 2.2.5. OpenCode 1.x has different flags; ask the user to
upgrade with `opencode upgrade`.

## Models

A model is `provider/model`, such as `opencode/deepseek-v4.1-flash-free`.
`opencode models` lists one per line. Pick the pool in this order:

1. Models the user named in the request.
2. The saved pool: the `models` list in `$XDG_CONFIG_HOME/swe/opencode.json`
   (default `~/.config/swe/opencode.json`). When the user names models to
   keep, check that each one is in `opencode models`, then write the file as
   `{"models": ["<provider/model>", ...]}`. Never write OpenCode's own config.
3. The default: `opencode/deepseek-v4.1-flash-free`, which is free. For a
   race or a retry, add other free Zen models: the `opencode/...-free` lines
   in `opencode models`.

To see a model's effort variants, read `variants` in its entry in
`opencode api --standalone model.list`. The output is large JSON, so filter
it for the model; do not read it whole.

Use a paid model only when the user named it. Give workers different models
from the pool in turn.

## Effort

Append the effort to the model as a variant: `-m <provider/model>#high`.
Most models offer `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`.
A variant the model does not have fails at once with exit 1 and
`Variant unavailable for <model>: <level>`. Then run the worker again at the
nearest level the model has, the higher one on a tie, or with no variant if
it has none. This rerun is not the worker's one retry.

## Run a worker

The same command serves a questions worker and a delegate. Run it from your
worktree as one plain command, with no `cd`, `env`, or `timeout` in front,
so that a narrow permission rule for `opencode run` can match it (see
[host-permissions.md](host-permissions.md)).

```sh
opencode run --standalone --auto -m <provider/model>#<effort> -f <run>/<id>.md -- "Follow the attached brief." < /dev/null > <run>/<id>.txt 2> <run>/<id>.log
```

- OpenCode has no OS sandbox. A worker runs as the user: it can run any
  command, read and change any file the user can, and reach the network.
  The worktree is only its working directory. Put nothing in a brief or the
  repository that the user has not agreed to send to the provider.
- `--standalone` starts a private server, so parallel workers share none.
- `--auto` approves every tool that the user's OpenCode config does not
  deny. In OpenCode 2.2.5, `opencode run --help` says: "Auto-approve
  permissions that are not explicitly denied". Without it, a tool that needs
  approval cannot run headless.
- OpenCode has no time limit of its own. Some models take several minutes.
  Stop a questions worker after 10 minutes and a delegate after 60: stop
  its background command with your host's tool for that. Then run
  `pgrep -fl "opencode run --standalone"`, and stop any process left from
  that worker, because its private server can outlive the command.
- Before the first run, check every OpenCode config that applies for
  `"share": "auto"`: the user's (`~/.config/opencode/opencode.json` or
  `.jsonc`), the project's `opencode.json`, and the file that
  `$OPENCODE_CONFIG` names. With it, every session is published as a link;
  ask the user before you run.

## Read the result

With the default output format, stdout holds only the final answer, and the
tool trace goes to stderr.

- `ok`: exit 0 and a non-empty `<run>/<id>.txt`.
- `timeout`: you stopped the worker at its limit.
- `error`: any other result. The end of `<run>/<id>.log` says why.

For each tool call as a JSON event, add `--format json`. The last `text`
event then holds the answer, and an `error` event holds a failure.

## Gotchas

- Zen models need network access to `opencode.ai`. Some cloud sandboxes block
  it, so run the workers on the user's computer.
- OpenCode writes its log under `~/.local/share/opencode`. A sandbox that
  blocks that path stops `opencode` before it starts.
