---
name: using-rex
description: "How agents work in the Rex terminal: which commands get a pane, how to launch, wait on, and label blocks, and how to watch a pane, work on other hosts, and avoid known traps. Use when REX_SESSION is set and you start a command that may run for minutes, or open, watch, or arrange a pane."
---

# Using the Rex terminal

Rex's own `rex` skill teaches the CLI; run `rex skill show` for its guide.
This skill covers how we work in Rex. The [reference](references/USING-REX.md)
has the commands for each item. Paths such as `../../scripts/wait-status.lua`
resolve against this skill's real folder, with symlinks resolved.

## When it applies

Rex is in play when `REX_SESSION` is set. In a headless run, such as
`claude -p`, `codex exec`, `opencode run`, or Claude Code with
`CLAUDE_CODE_ENTRYPOINT=sdk-cli`, use your shell tool and open no panes.
A subagent opens, renames, and arranges no panes or sessions.

## Which commands get a pane

Open a block for:

- a command you expect to run longer than about 2 minutes;
- a server or a watcher;
- a training or eval run;
- a job on another host.

Run everything else in your shell tool: reads, searches, git, quick builds and
tests, and a tool's help, version, or status.

In auto or bypassPermissions mode, a background command (Claude Code
`run_in_background`) opens as a minimized floating pane in your tab after 1.5
seconds. Commands that finish sooner open no pane. At startup, the pane prints
a dim one-line header with the label and start time, shows a working spinner,
ends `done` or `error` with the exit code, and closes when the command exits.
Start it in the background as usual; open no block for it. Set
`REX_AGENTS_MIRROR_DELAY_MS` to adjust the open delay in milliseconds, or set
`REX_AGENTS_MIRROR=0` to turn the mirror off.

A long training or eval run is the exception: give it a standalone block even
in auto mode. A mirrored background command ends with the agent session, and a
block does not, so the run survives a pause and you can resume it.

## Pass the agent's environment

A block starts from the login shell's environment, not from yours. A run that
calls Claude Code must get your `CLAUDE_CONFIG_DIR`, or it bills the login
shell's default account. Pass it, and any other variable the run needs, with
`/usr/bin/env`:

```sh
rex run --shell=none -- /usr/bin/env CLAUDE_CONFIG_DIR="$CLAUDE_CONFIG_DIR" <absolute program path> <args>
```

## Find where you are

- `REX_SESSION` and `REX_BLOCK` come from the terminal that started your
  process, and they can be stale. Before you open a pane, check that
  `REX_BLOCK` exists and that its process is an ancestor of yours. When it is
  not, tell the user instead of guessing a target.
- The session is yours when you created it, or when your pane is its only
  block. Otherwise you share it, as in the user's command-center session.

## Name what you own

- Label each block you create `[<agent>] <task>`, such as
  `[claude] kalin full run`. The user's own panes never start with brackets,
  so the prefix tells them apart at a glance.
- Never rename a shared session, and never rename a block you did not create.
  In a session that is yours, you can label the session and its tabs after
  their work.
- Close a block you created when you no longer need it. Close or kill a
  session only when the user asks.

## Launch

Start a program with `--shell=none` and its absolute path, such as
`rex run --shell=none -- /opt/homebrew/bin/uv run train.py`. Leave out
`--interactive`: it reads the shell's startup files, and those can start a
proxy that replaces the command.

Each layout has a cost. Mix them as the task needs.

- **A tab per step.** `rex run --wait --keep-open` without `--split` returns
  the exit status, and the output stays readable. Tabs accumulate, which suits
  a session that is yours.
- **A split beside your pane.** `--split=below -b "$REX_BLOCK"` keeps the work
  next to you. It suits a shared session.
- **A persistent shell** keeps state between commands: the directory,
  environment, a REPL or debugger, or a shell the user logged in to. Rex
  reports no exit status for each command in a shell. Read it from Atuin.
- **A long-running process**, such as a server, watcher, or training run.
  Leave out `--wait`, and wait on it as the next section says.

Put several commands of one step in one `nu -c` call, so the step stops at
the first failure.

## Wait on events

Wait on Rex events, never on a sleep loop or a capture on a timer.

- A block whose program reports its status (Claude Code, a mirror block):
  `rex do -s <session> ../../scripts/wait-status.lua block=<block>`. It reads
  the current status first, so a status reported before the wait began is not
  missed while the block exists. A mirror block closes 1 s after its command
  ends; a wait that starts later prints `block not found` and exits 1. It prints one JSON object with the state, kind, message, and
  `updated_at`, and exits 2 on timeout. Pass `after=<updated_at>` of the last
  record you acted on to wait for a newer one.
- A block whose program exits when done: `rex wait --for <duration> <block>`.
- Run a long wait in the background where the harness wakes you when it ends
  (Claude Code `run_in_background`).
- `rex do ../../scripts/agent-inbox.lua` lists every block in state `blocked`,
  `done`, or `error`, on this server and on each host.

## Watch a pane the user hands you

A block ID the user hands you is a pane they work in while you watch.
Capture it first, then watch its events in the background, so you see each
command they run. Type into it only when they ask, and only at a shell
prompt.

## Other hosts

Add `-S <host>` to each `rex` command; `rex hosts` lists the labels. Your
`REX_*` IDs do not apply there, so pick or create a labelled session on that
host. Use SSH only for a host with no Rex server.

## Drive another agent

To start, brief, watch, and collect another agent session in a block, use
the `drive-agent` skill.

## Traps

- Claude Code's `/bg` moves the conversation to a new process that inherits
  the environment of the background supervisor. Its `REX_*` IDs then point at
  an unrelated session, and its panes land there. To move a conversation to
  another Rex session, run `claude --resume <id>` in that session.
- A block ID copied from earlier in the conversation can name a pane that is
  gone. Read the current state before you target it.
