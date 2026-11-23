# Rex commands and facts

Commands for each item in [the skill](../SKILL.md). Replace each
`<placeholder>`. `<plugin>` is the `rex-agents` plugin folder, two levels
above the skill folder. Rex's own guide (`rex skill show`) and
`rex <command> --help` cover every other option.

## Find where you are

Check that `REX_BLOCK` is your pane: its process must be an ancestor of yours.

```sh
nu -c 'let pane = (rex block call -s $env.REX_SESSION -b $env.REX_BLOCK process | from json | get child.pid); let procs = (ps); mut pid = $nu.pid; mut mine = false; while $pid > 1 { if $pid == $pane { $mine = true; break }; let row = ($procs | where pid == $pid); if ($row | is-empty) { break }; $pid = ($row | get 0.ppid) }; $mine'
```

`false`, or an error that the block is not found, means the IDs are stale.

Count the blocks in your session. `1` means the session is yours.

```sh
nu -c 'rex block ls -s $env.REX_SESSION --json | from json | get blocks | length'
```

See the session's label, tabs, and layout:

```sh
rex session inspect "$REX_SESSION" --json
```

## Name what you own

Label a block when you create it with `--label "[<agent>] <task>"`, or later:

```sh
rex block rename <block> "[<agent>] <task>"
```

Only in a session that is yours:

```sh
rex session rename <session> "[<agent>] <task>"
rex window rename -s <session> <window> "<name>"
```

## Lay out and run work

Start a program with `--shell=none` and its absolute path (`command -v <name>`
prints it). Without a shell, a pipeline or `&&` needs `nu -c`, with the
absolute path of `nu`. `rex run --json` prints the new block's ID as
`block_ids[0]`.

A tab per step. `--wait` returns the exit status, and `--keep-open` keeps the
output after the command ends:

```sh
rex run -s "$REX_SESSION" --wait --keep-open --focus=false --shell=none --label "[<agent>] <step>" -- <abs nu> -c '<cmd>; <cmd>'
```

A split below your pane: add `--split=below -b "$REX_BLOCK" --ratio 30` to
the same command.

Read a block's output, and close it when you no longer need it:

```sh
rex capture -s "$REX_SESSION" -b <block> --trim
rex block close -s "$REX_SESSION" <block>
```

A persistent shell. Open it once, then type each command into it:

```sh
rex run -s "$REX_SESSION" --focus=false --shell=none --label "[<agent>] shell" -c <dir> -- <abs nu>
rex send -s "$REX_SESSION" -b <block> '<cmd>'
rex send-key -s "$REX_SESSION" -b <block> enter
```

`rex block call -s "$REX_SESSION" -b <block> process` shows the foreground
process. When it is the shell again, the command is done. Atuin records each
command's exit status. Use the `atuin_history` MCP tool first. In the CLI,
pass `--search-mode fulltext`:

```sh
atuin search --search-mode fulltext --limit 1 --format '{exit}\t{command}' '<distinctive part of the command>'
```

Atuin keeps no terminal output for a command that an agent ran. Read that
output in the agent's thread: `atuin_threads_search`, then
`atuin_threads_read`.

## Wait on events

A block whose program reports its status, such as Claude Code or a mirror
block. Run it in the background:

```sh
rex do -s "$REX_SESSION" <plugin>/scripts/wait-status.lua block=<block> timeout=600
rex do -s "$REX_SESSION" <plugin>/scripts/wait-status.lua block=<block> after=<updated_at>
```

| Argument | Meaning |
| --- | --- |
| `block` | Required. The block to watch. `-s` must name its session. |
| `timeout` | Seconds to wait. Default 600. Exit 2 when it passes. |
| `states` | States that end the wait. Default `done,blocked,error,idle`. |
| `after` | An RFC 3339 time. Only a record newer than it ends the wait. Pass the `updated_at` of the last record you acted on. |

The output is one JSON object: `event` (`status`, `child_exited`, or
`timeout`), `state`, `kind`, `msg`, `app`, `updated_at`, and `exit_code` for
`child_exited`. A block whose program already exited returns
`child_exited` at once.

A closed block cannot be waited on: the script prints `block not found` and
exits 1. A mirror block closes 1 s after its command ends, so its status can
be waited on only until then. Start the wait while the command runs.

A block whose program exits when done:

```sh
rex wait -s "$REX_SESSION" --for 10m <block>
```

A wait that times out does not tell you whether the command passed. Check
`process` for `last_exit`.

Every block that needs a look, on this server and on each host:

```sh
rex do <plugin>/scripts/agent-inbox.lua
```

## Watch a pane the user hands you

Capture the pane, then run this in the background. It prints a line for each
command start, each return to the prompt, each program status change, and
the pane's close. Replace `<block>`:

```sh
nu -c 'let b = "<block>"; rex events -s $env.REX_SESSION --json | lines | each {|l| let e = ($l | from json | get payload.event); let p = $e.payload; if ($p.block_id? != $b) { return }; if $e.type == "block_closed" { print "pane closed"; exit 0 }; match $p.name? { "title_changed" => { print $"title: ($p.payload.title)" }, "pwd_changed" => { print "prompt returned" }, "program_status_changed" => { print $"status: ($p.payload.record? | to nuon)" }, "child_exited" => { print $"shell exited ($p.payload.exit_code)"; exit 0 }, _ => {} } } | ignore'
```

A `title:` line shows the command that started. `prompt returned` means it
finished: capture the pane and read the new output. Use the longest timeout
your tool allows, and start the watch again each time it ends, until the user
releases or closes the pane.

## Other hosts

```sh
rex hosts
rex -S <host> new "[<agent>] <task>" --json
rex -S <host> run -s <session> --wait --keep-open --focus=false --label "[<agent>] <step>" -- nu -c 'cd <dir>; <cmd>'
```

A terminal on another host starts in the home directory, so change directory
inside the command.

## Mirror blocks

In the `auto` and `bypassPermissions` permission modes, the `rex-agents`
PreToolUse hook rewrites a background Bash call into this form, so its output and exit status pass through unchanged:

```sh
{ ( :; <cmd>
 ); printf '\n__rex_rc=%d\n' "$?"; } 2>&1 | <abs runtime> <plugin>/scripts/rex_mirror.ts '<label>' <session id>
```

`rex_mirror.ts` waits 1.5 seconds (`REX_AGENTS_MIRROR_DELAY_MS` overrides the
delay in milliseconds; `0` opens at once), then opens a minimized floating pane
labelled `[claude] <description>` (`[claude:sub]` for a subagent). The pane
opens in the agent's tab when `REX_BLOCK` is set and `rex block inspect` returns
that block's window; otherwise Rex chooses where it opens. Commands that exit
before the delay open no pane. If Rex refuses the floating layer,
`rex_mirror.ts` falls back to `rex run`. If a `rex` call times out or is
stopped before its reply, the outcome is unknown: `rex_mirror.ts` opens no
second pane, and writes the exit line for a pane that Rex may still open late.
If no pane opens, the command's log stays in `TMPDIR` with mode 0600. At
startup, the viewer prints a dim one-line header with the label and local start time, shows
the output live from byte 0, reports `working`, then `done` or `error` with
`<label>: exit <n>`, and closes the block. Permission rules still see `<cmd>`.
Commands that start with `rex ` stay unchanged, so a driven agent's wait gets
no pane of its own. The SessionEnd hook closes a mirror block whose close
failed. `REX_AGENTS_MIRROR=0` turns the mirror off.

## Facts

- Each terminal gets the `REX_SESSION` and `REX_BLOCK` of the session that
  holds it. A process keeps the values it started with.
- A client, such as the Mac app, can watch every session. The Activity
  sidebar (cmd+.) groups program status by session, so the user can see a
  blocked agent in another session without switching to it.
- Rex has no session groups or tags. Labels and order are the only way to
  tell sessions apart.
- A server holds at most 64 sessions and 64 tabs per session.
- After a server restart, Rex restores sessions and layouts, but not the
  programs that ran in them.
- Client actions, such as `session.select`, which shows a session in the
  app, need Remote Control. It is off by default; leave the setting to the
  user.
- A `rex do` script receives events from the moment it starts, so a
  `rex.wait` after a read misses nothing that happened in between.
- An exited block started with `--keep-open` has no `child` in `process`, a
  `last_exit`, and no `working` or `blocked` records.

## `/bg` and the Rex IDs

The `REX_SESSION` and `REX_BLOCK` values that a Claude Code process sees when
the conversation starts in a fresh Rex session (checked 2026-11-08):

| Case | Process | IDs it sees |
| --- | --- | --- |
| Started in the origin session | origin | origin |
| After `/bg`, attached from a new session | new, under the supervisor | an unrelated session |
| Stopped, then `claude attach` from the new session | new, under the supervisor | the same unrelated session |
| `claude --resume <id>` in the new session | new, in that terminal | the new session |

The unrelated session is the one that started the background supervisor.
`/bg` also leaves the origin session open with no blocks.
