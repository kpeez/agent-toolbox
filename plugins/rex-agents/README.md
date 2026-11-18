# rex-agents

rex-agents makes the [Rex terminal](https://www.superlogical.com/rex) the place
where agent work runs and where you watch it, on the Mac and in Rex for iOS.
Hooks do the work, so it does not depend on what the agent remembers:

- Each background command that Claude Code starts in auto mode gets its own
  Rex tab. The tab shows the output live, with a working spinner, and ends
  `done` or `error` with the exit code. The agent gets the same output and
  exit status as before, and permission rules still see the original command.
- When the session ends, its `done` tabs close. Its `error` tabs stay for you.
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
| `scripts/rex_mirror.py`, `scripts/rex_mirror_view.py` | The mirror: pass output through and show it in a block |

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

The hooks need `uv` and `rex` on PATH. Outside Rex (`REX_SESSION` unset), they
do nothing.

## Turn the mirror off

Set `REX_AGENTS_MIRROR=0` in the environment before you start Claude Code.
Background commands then run unchanged.

The mirror applies only in the `auto` and `bypassPermissions` permission
modes. In a mode that prompts, the wrapped command would not match your allow
rules, so an allowed background command would ask for approval. Those modes
keep the command unchanged.

## Test

```text
uv run -m unittest discover -s plugins/rex-agents/scripts/tests
```

The tests run the wrapper on 10 command shapes in zsh and bash, check the exit
status for a stream without the status marker, and check each hook decision.
