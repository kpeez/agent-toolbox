# rex-agents

rex-agents makes the [Rex terminal](https://www.superlogical.com/rex) the place
where agent work runs and where you watch it, on the Mac and in Rex for iOS.
Hooks do the work, so it does not depend on what the agent remembers:

- Each background command that Claude Code starts in auto or
  bypassPermissions mode opens as a minimized floating Rex pane after 1.5
  seconds: in the agent's tab when `REX_BLOCK` is set and `rex block inspect`
  finds its window, otherwise where Rex chooses. Commands that finish sooner
  open no pane. At startup,
  the pane prints a dim one-line header with the label and start time, shows
  the output live with a working spinner, ends `done` or `error` with the exit
  code, and closes when the command exits. The agent gets the same output and
  exit status as before, and permission rules still see the original command.
- A pane whose close fails stays; the SessionEnd hook retries the close when
  the session ends.
- A session in a Rex pane starts with the `using-rex` skill in context.
- A subagent is told to leave panes and sessions alone.

| Skill | What it does |
| --- | --- |
| `using-rex` | Which commands get a pane, how to launch and label blocks, how to wait on Rex events, and known traps |
| `drive-agent` | Start, brief, watch, and collect another agent session in a Rex block |

| Script | What it does |
| --- | --- |
| `scripts/wait-status.lua` | `rex do` script: wait until a block reports a settled status, with no sleep loop |
| `scripts/agent-inbox.lua` | `rex do` script: list every blocked, done, or error block on this server and each host |
| `scripts/rex_mirror.ts`, `scripts/rex_mirror_view.ts` | The mirror: pass output through and show it in a block |

The Rex CLI reference is Rex's own `rex` skill (`rex skill setup`). This plugin
covers how agents work in Rex.

## Install

Claude Code (skills and hooks):

```text
/plugin marketplace add kpeez/agent-toolbox
/plugin install rex-agents@agent-toolbox
```

Codex CLI and Antigravity CLI load the skills only. Codex and agy run no
rex-agents hooks yet.

```text
codex plugin marketplace add kpeez/agent-toolbox
codex plugin add rex-agents@agent-toolbox
agy plugin install https://github.com/kpeez/agent-toolbox/tree/main/plugins/rex-agents
```

The hooks need `bun`, or Node 22.18 or later, and `rex`, on PATH. Without a
runtime, each hook that starts shows a hook error that names the fix. Outside
Rex (`REX_SESSION` unset), the hooks make no change, and the Bash hook starts
no runtime.

## Mirror settings

Set `REX_AGENTS_MIRROR=0` in the environment before you start Claude Code to
turn the mirror off. Background commands then run unchanged.

Set `REX_AGENTS_MIRROR_DELAY_MS` to change how long a command runs before the
pane opens. The default is `1500` milliseconds. Set `0` to open at once.

The mirror applies only in the `auto` and `bypassPermissions` permission
modes. In a mode that prompts, the wrapped command would not match your allow
rules, so an allowed background command would ask for approval. Those modes
keep the command unchanged.

## Test

```text
bun test plugins/rex-agents/scripts/tests
node --test plugins/rex-agents/scripts/tests/
```

The tests run the wrapper on 12 command shapes in zsh and bash, check the exit
status for a stream without the status marker, and check each hook decision.
They also kill the mirror mid-stream, check that an exited viewer closes its
block, and run every hook under node. Both runtimes run the same files.
