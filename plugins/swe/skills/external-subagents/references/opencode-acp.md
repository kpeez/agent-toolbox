# OpenCode ACP bridge (`opencode/acp` direct sessions)

A Python 3 stdlib-only MCP stdio server
(`<plugin-root>/mcp/opencode_acp_bridge.py`) that runs **one long-lived
`opencode acp --pure` child** (ACP v1, JSON-RPC over stdio) and multiplexes
independent agent sessions across MCP tools. Verified protocol sources:
[agentclientprotocol.com](https://agentclientprotocol.com/) (schema,
prompt-turn, tool-calls, session-setup, session-config-options,
model-config-category) and [opencode.ai/docs/acp](https://opencode.ai/docs/acp/).
It installs nothing on the host and has no native Codex/host integration.

## Verification snapshot — 2026-09-11

- 19 offline entrypoint tests passed, including concurrent waits, follow-ups,
  cancellation stalls, child death, output limits, cwd routing, and permissions.
- Codex CLI 0.154.0 loaded the installed SWE 1.17.1 bridge through an explicit
  MCP registration. OpenCode 1.18.30 ran two concurrent, tool-enabled read-only
  sessions against the selected worktree, retained follow-up context, paged
  output from the prior cursor, and closed both ACP sessions cleanly.
- The non-auto `opencode run --dir` fallback also passed a provider-backed
  prompt with `deepseek-v4.1-flash`.
- Cross-restart recovery, write-enabled execution, and native host-agent parity
  were not verified. This is a local bridge, not a performance benchmark.

Connect an MCP client as:

```sh
python3 <plugin-root>/mcp/opencode_acp_bridge.py --help
python3 <plugin-root>/mcp/opencode_acp_bridge.py \
  --opencode opencode \
  --allowed-root /abs/allowed/root \
  --permission-config /abs/operator-permission.json \
  --max-sessions 8 --max-output-chars 200000 \
  --startup-timeout 30 --prompt-timeout 600 \
  --cancel-timeout 10 --stderr-limit 64000
```

## Commands and configuration

| Flag | Default | Meaning |
| --- | --- | --- |
| `--opencode` | `opencode` | OpenCode executable to launch. Env (e.g. `OPENCODE_API_KEY`) is inherited unchanged, except for the policy noted below. |
| `--opencode-arg` | `acp --pure` | Extra child argument; repeatable and **replaces** the default (point a test at a fake peer this way). |
| `--allowed-root` | none (required) | Absolute directory a new agent's `cwd` must resolve under; repeatable. **Routing only, not a sandbox.** |
| `--permission-config` | none | Path to a JSON permission OBJECT, e.g. `{"*":"deny","read":{"/allowed/**":"allow"}}` — not an entire OpenCode config. Opt-in tool policy; not a sandbox. |
| `--max-sessions` | 8 | Maximum concurrent agents; enforced before each spawn. |
| `--max-output-chars` | 200000 | Transcript characters retained per agent (tail-truncated). |
| `--startup-timeout` | 30 | Bound on `initialize`/`session/new` round-trips. |
| `--prompt-timeout` | 600 | Seconds before a prompt is cancelled via `session/cancel`; `0` disables. |
| `--cancel-timeout` | 10 | Seconds to wait for a cancelled prompt before reporting a stall. |
| `--stderr-limit` | 64000 | Bytes of child stderr retained for diagnostics. |

`--help` and `--version` are supported. Offline test suite:
`python3 plugins/swe/mcp/tests/test_opencode_acp_bridge.py` (drives the real
entrypoint against `tests/fake_opencode_acp.py`; no network, no paid models).

## Tool access policy

The bridge controls the child through `OPENCODE_CONFIG_CONTENT`:

- Without `--permission-config`, permission is **deny-all**, even when the
  parent environment already grants `permission` or `tools`. Inherited config
  never implicitly opts into tools.
- With `--permission-config`, the file is a single permission object, not a
  whole OpenCode config. A safe narrow example that keeps everything denied
  except reading under one tree:
  ```json
  {"*": "deny", "read": {"/allowed/**": "allow"}}
  ```
- Unrelated inherited settings such as `model` are preserved, but the bridge
  forces `share` disabled and build mode under the same permission policy.
  It applies that policy to every inherited agent and always disables `task`,
  so the primary cannot escape it through a more-permissive nested subagent.
  Non-deny wildcard rules that could match `task` are rejected at startup.
- This is configuration layering, not an OS sandbox: granted OpenCode tools run
  with OpenCode's own permissions and reach wherever that policy allows.
- ACP `session/request_permission` callbacks are **always denied** — a `reject_*`
  option when offered, otherwise `cancelled` — and each denial is recorded on
  the agent as `blocked_reasons`. There is no `--auto` and no bypass flag; the
  bridge never authenticates or writes OpenCode config.

## Tools

- `spawn_agent(prompt, cwd, model?)` — creates the ACP session (`session/new`
  with the validated absolute cwd) and immediately fires `session/prompt`.
  Returns `{agent_id, session_id, state:"running"}` promptly. An explicit
  `model` is applied with `session/set_config_option` on OpenCode's `model`
  config option (confirmed live: id `model`, category `model`, values such as
  `opencode/big-pickle`), including values nested in groups. Unknown models, or
  an agent that advertises no model option, produce an error — never a silent
  fallback. No model requested → OpenCode's configured default.
- `send_message(agent_id, prompt)` — follow-up over the same retained session.
  Rejected with an error while running; prompts are never queued or dropped.
- `get_agent(agent_id, cursor?)` — state, stop reason, error,
  `blocked_reasons`, and bounded transcript text. `output.next_cursor` is an
  opaque char offset for paging; `dropped_chars`/`total_chars` describe
  tail truncation; `has_more` is true only while running.
- `list_agents()` — snapshots plus the configured limit.
- `wait_agents(agent_ids, timeout)` — waits (≤60 s) until none are running.
  Runs on its own request; other tool calls are never blocked behind it.
- `interrupt_agent(agent_id)` — sends `session/cancel` and answers any pending
  permission request as `cancelled`. Returns immediately; state stays
  `running` until the turn actually resolves, then `stop_reason: "cancelled"`.
- `close_agent(agent_id)` — cancels a running turn (waits up to
  `--cancel-timeout`; reports `cancel_stalled: true` if it will not resolve —
  it never tears down unrelated sessions), releases the slot, and sends
  `session/close` when OpenCode advertises `sessionCapabilities.close`
  (confirmed supported). If the ACP turn is still open and `session/close` is
  rejected, the slot is kept and new prompts are refused instead of orphaning
  the session.

## Lifecycle and limits

- States: `running` → `idle` (turn resolved) or `failed` (child died, prompt
  errored, or cancel stalled). `error` carries details.
- Child death marks every session failed — both idle and running agents — with
  the exit code and a bounded stderr tail; new spawns error until you restart
  the bridge. There is no auto-restart and no "kill all sessions" path.
- A prompt timeout cancels the turn; a stale watchdog never cancels a later
  turn on the same session.
- Bounded everything: transcript chars, stderr bytes, timeouts, session slots.
- Shutdown (stdin EOF or SIGTERM): best-effort cancels for running turns,
  bounded `session/close` for idle ones, then terminate/reap the child.

## Not native parity

- Tool names are MCP names only; there are no native Codex/host tool calls.
- ACP `fs/*` and `terminal/*` client capabilities are deliberately not
  advertised and are refused if an agent calls them anyway.
- `session/load|resume|fork|list` are advertised by OpenCode but unused here;
  sessions are created fresh per `spawn_agent`. No worktree is created
  automatically — pass `cwd` explicitly.
- The allowed-root check is path routing, not filesystem isolation.
- Some OpenCode TUI commands (e.g. `/undo`, `/redo`) do not work over ACP per
  OpenCode's docs.
