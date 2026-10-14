# Claude Code mods

Mods add panes and bands to the Claude Code interface. They run only in Claude
Code, so only the Claude catalog lists them. Each mod is its own plugin under
[`claude-mods/`](../claude-mods/).

| Mod | Install | Open | What it shows |
| --- | --- | --- | --- |
| `activity` | `claude plugin install activity@agent-toolbox` | `/activity` | Each tool call with its status and duration. Click a call for its full input and error. |
| `subagents` | `claude plugin install subagents@agent-toolbox` | `/subagents` | A sprite per subagent with its type, task, latest tool call, and elapsed time. Opens on the first subagent when the screen has room. |
| `session-panel` | `claude plugin install session-panel@agent-toolbox` | `/panel` | Tabs for an overview timeline, each subagent's prompt and answer, each shell command and output, and the files touched. |

In `session-panel`, the **ask** button attaches a command or an agent run to
your next prompt. `/panel demo` loads sample data.
