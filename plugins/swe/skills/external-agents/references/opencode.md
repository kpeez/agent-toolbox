# OpenCode

OpenCode reaches models through the providers the user connected: OpenCode
Zen, OpenCode Go, GitHub Copilot, OpenAI, local Ollama, and others. Every
provider takes the same command.

## Check

Run `opencode --version`. The skill needs OpenCode 2.x (npm `@opencode/cli`)
and was tested on 2.2.5 and 2.2.6. OpenCode 1.x has different flags; ask the user to
upgrade with `opencode upgrade`.

Run `opencode service status`. When the service runs, it prints its local URL
(such as `http://127.0.0.1:49374`). The background service starts workers
faster (1–2s start) and keeps prompt caching across fix rounds. If it is
stopped, start it once with `opencode service start`, or pass `--standalone`
to start a private server per run.

Run `opencode debug config` and confirm that agents named `scout` and `builder`
exist. If either is missing, stop and show the user these definitions to add
to their OpenCode config. The git patterns stop plain mistakes, not a
determined bypass.

```jsonc
{
  "agent": {
    "scout": {
      "mode": "primary",
      "model": "<provider/model>",
      "permission": { "edit": "deny", "bash": "deny" }
    },
    "builder": {
      "mode": "primary",
      "model": "<provider/model>",
      "permission": {
        "edit": "allow",
        "bash": {
          "*": "allow",
          "*git*push*": "deny",
          "*git*merge*": "deny",
          "*git*rebase*": "deny",
          "*git*reset*": "deny",
          "*git*stash*": "deny",
          "*git*switch*": "deny"
        }
      }
    }
  }
}
```

## Roles and models

Use `--agent scout` for questions and `--agent builder` for a delegate.
Read `$XDG_CONFIG_HOME/swe/opencode.json` (default
`~/.config/swe/opencode.json`) for the role's ordered fallback list:

```json
{"roles": {"scout": ["<provider/model>", "<provider/model>"], "builder": ["<provider/model>", "<provider/model>"]}}
```

Use the first entry as the default and later entries as fallbacks. Pass the
chosen entry with `-m`; it overrides the agent's configured model. If the file
or role is missing, or its list is empty, omit `-m` and use the agent's model.
`opencode models` lists available model IDs. Never write OpenCode's own config.

To see a model's effort variants, read `variants` in its entry in
`opencode api model.list` (or `opencode api --standalone model.list` if the
service is stopped). The output is large JSON, so filter it for the model;
do not read it whole.

## Effort

Append the effort to the model as a variant: `-m <provider/model>#high`.
Most models offer `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`.
A variant the model does not have fails at once with exit 1 and
`Variant unavailable for <model>: <level>`. Then run the worker again at the
nearest level the model has, the higher one on a tie, or with no variant if
it has none. This rerun is not the worker's one retry.
When you omit `-m`, the agent's configured model and effort apply.

## Run a worker

Run the scout from the lead's current directory and the builder from the
lead's task worktree. Run one plain command, with no `cd`, `env`, or `timeout`
in front and no `nu -c` or `bash -c` around it, so a narrow permission rule for `opencode run` can match it (see
[host-permissions.md](host-permissions.md)).

```sh
opencode run --auto --format json --agent <scout-or-builder> -m <provider/model>#<effort> -f <run>/<id>.md -- "Follow the attached brief." < /dev/null > <run>/<id>.json 2> <run>/<id>.log
```

- When the background service runs, `opencode run` connects to it
  automatically. The daemon executes the worker in the client's working
  directory, so parallel workers stay isolated.
- Pass `--standalone` only when the background service is stopped and you do
  not want to start it, in CI or disposable containers, or when you need hard
  process-level crash isolation.
- Omit `-m` when the role has no list. For delegate sessions and review
  rounds, see [Sessions](#sessions) below.
- For a questions worker whose output should stay out of the user's interactive
  session list, add `--archived`.
- OpenCode has no OS sandbox. The scout cannot edit or run shell commands;
  the builder has full tools subject to its config. The worktree is only its
  working directory. Send only content the user agreed to send to the provider.
- `--auto` approves every tool that the user's OpenCode config does not
  deny. In OpenCode 2.2.5, `opencode run --help` says: "Auto-approve
  permissions that are not explicitly denied". Without it, a tool that needs
  approval cannot run headless.
- OpenCode has no time limit of its own. Some models take several minutes.
  Stop a questions worker after 10 minutes and a delegate after 60: stop
  its background command with your host's tool for that. When running with
  `--standalone`, also run `pgrep -fl "opencode run --standalone"` and stop any
  leftover process, because a private server can outlive the command.
- Before the first run, check every OpenCode config that applies for
  `"share": "auto"`: the user's (`~/.config/opencode/opencode.json` or
  `.jsonc`), the project's `opencode.json`, and the file that
  `$OPENCODE_CONFIG` names. With it, every session is published as a link;
  ask the user before you run.

## Sessions

OpenCode manages sessions on the background service. Each session has an ID
starting with `ses_` and its own conversation history.

- **Session ID format.** A session ID must start with `ses_` (such as
  `--session ses_<stamp>_<id>`). OpenCode rejects any other prefix.
- **Start a delegate session.** On a builder's first run, pass
  `--session ses_<stamp>_<id> --title "<title>"`.
- **Resume a session.** For a review round or follow-up turn, pass the same
  `--session ses_<stamp>_<id>` and attach only `<run>/<id>-review-<n>.md` with
  `-f`. Do not re-send the original brief. The worker remembers all previous
  turns, tool results, and git commits. Resuming on the running service hits
  prompt cache and starts in 1–2 seconds.
- **List sessions.** Run `opencode session list` to inspect top-level
  sessions in the current project directory.
- **Export session history.** Run `opencode session export <session-id>` to
  export turns, tool calls, and token counts as JSON. Pass `--sanitize` to
  redact sensitive content.
- **Delete a session.** Run `opencode session delete <session-id>` to remove
  a finished worker session and its child sessions from daemon memory and
  disk.

## Read the result

Read the JSON events in `<run>/<id>.json`. The last `text` event holds the
final answer. An `error` event holds a failure; also inspect the log.
Classify results in this order:

- `timeout`: you stopped the worker at its limit.
- `auth_failed`: a JSON `error` event has `error.type` of `provider.auth`,
  for example with the message `Request failed: 401`. Tell the user which
  provider needs `opencode auth login`.
- `rate_limited`: HTTP 429 or a quota message appears in the log or a JSON
  error event.
- `ok`: exit 0 and a non-empty final `text` event, with no error event.
- `error`: any other result. The end of `<run>/<id>.log` can say why.

## Gotchas

- A session ID that does not start with `ses` fails at once with
  `Expected a string starting with "ses"`, with no answer and no tool calls.
- Zen models need network access to `opencode.ai`. Some cloud sandboxes block
  it, so run the workers on the user's computer.
- OpenCode writes its log under `~/.local/share/opencode`. A sandbox that
  blocks that path stops `opencode` before it starts.
