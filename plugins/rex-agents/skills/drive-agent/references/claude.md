# Claude Code

Claude Code reports `idle` at start, `working` during a turn, `done` at the
end of a turn, and `blocked` with `kind=permission` at a permission prompt.

## Launch

```sh
rex run -s <session> --focus=false --keep-open --shell=none --label "[claude] <task>" --cwd <worktree> --json -- "$(command -v claude)" [flags]
```

Useful flags:

| Flag | Use |
| --- | --- |
| `--permission-mode <mode>` | `manual` (asks before each unallowed action), `acceptEdits`, `plan`, or `auto`. Without it, the user's default mode applies. |
| `--model <alias>` | A cheaper model for mechanical work. |
| `--plugin-dir <dir>` | Load a plugin from a folder for this session only. |
| `--settings <file or json>` | Add settings, such as permission rules, for this session only. |

The child loads the worktree's `.claude/settings.json` and the user's own
settings. To test a setting without changing the user's files, pass it with
`--settings`.

## Trust dialog

A directory Claude Code has not seen before shows a trust dialog, and the
child does not report `idle` until it is answered. Its default is "No, exit".
Capture the screen to confirm it is the trust dialog. Then, only for a
directory you created for this task or the user's own project, choose "Yes":

```sh
rex send-key -s <session> -b <block> down enter
```

## Permission prompt

A prompt shows numbered choices with `❯` on the selected one. `enter` on
`1. Yes` approves this one action. `escape` refuses it.

## End

```sh
rex send -s <session> -b <block> '/exit'
rex send-key -s <session> -b <block> enter
```

`wait-status` then returns `child_exited`.
