# OpenCode

Script: [opencode_run.py](../scripts/opencode_run.py). Its docstring and
`--help` hold every flag.

OpenCode reaches models through the providers the user connected: OpenCode
Zen, OpenCode Go, GitHub Copilot, OpenAI, local Ollama, and others. Every
provider takes the same path.

## Check

Run `opencode --version`. The script supports OpenCode 2.x (npm
`@opencode/cli`) and 1.x (npm `opencode-ai`). Each worker starts its own
server (`run --standalone` on 2.x, `run --pure` on 1.x), so parallel workers
share no server.

## Models

Run `opencode_run.py prefs`. A saved `models` list is the user's pool, kept in
`$XDG_CONFIG_HOME/swe/opencode.json` (default `~/.config`). With no saved
list, the pool is every live OpenCode Zen stealth model, and a failed worker
falls back to `opencode/deepseek-v4.1-flash-free`. All of these are free.
A stealth model is a free Zen model under a code name, with no model family
and no version number in its ID.

Run `opencode_run.py models` to see each model OpenCode can reach, with its
provider, cost, stealth flag, and effort levels. When the user names models
or a provider, save that choice with `prefs --models <a,b>`. Use a paid model
only when the user named it. `run --models <a,b>` overrides the pool for one
run.

Tasks without a `model` take models from the pool in turn. A failed task runs
once more on the next model in the pool, because free models often hit rate
limits. A task's `effort` maps to the model's nearest variant.

## Permissions

The script layers a policy over `OPENCODE_CONFIG_CONTENT`. Read-only workers
may read, grep, glob, and list. `--edit` also allows edits and writes. Shell,
web, the 2.x code-mode `execute` tool, and nested subagents stay denied in
both modes. Sharing is off. This is OpenCode's permission config, not an OS
sandbox.

## Gotchas

- Zen models need network access to `opencode.ai`. Some cloud sandboxes block
  it, so run the workers on the user's computer.
- Some models are slow. A worker can take several minutes; `--timeout` is
  600 seconds per attempt by default.
- `--out <dir>` keeps each attempt's raw event stream for a failed worker.
