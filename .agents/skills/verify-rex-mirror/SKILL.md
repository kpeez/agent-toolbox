---
name: verify-rex-mirror
description: Model-check the rex-agents mirror block lifecycle with TLA+ (TLC) - the wrapper and its status marker, the mirror, the viewer and its close, the session-end pass, and a wait-status waiter - in every order of steps. Use when a change touches plugins/rex-agents/hooks/mirror_hook.ts, scripts/rex_mirror.ts, scripts/rex_mirror_view.ts, hooks/session_end.ts, or scripts/wait-status.lua, or when the check fails.
paths:
  - plugins/rex-agents/hooks/mirror_hook.ts
  - plugins/rex-agents/hooks/session_end.ts
  - plugins/rex-agents/scripts/rex_mirror.ts
  - plugins/rex-agents/scripts/rex_mirror_view.ts
  - plugins/rex-agents/scripts/wait-status.lua
---

# Verify the rex mirror lifecycle

In auto mode, the rex-agents hook pipes each background command into
`rex_mirror.ts`. The mirror opens a Rex block whose viewer shows `working`,
then `done` or `error` with the exit code, and then closes the block.

The promise: every mirrored block reaches `done` or `error` with the
command's own exit code, then closes, and a working block is never closed.

## The rules

`RexMirror.tla` checks each rule in every state that the steps can reach.

| Rule | Plain sentence | Harm when it breaks |
| --- | --- | --- |
| `ExitLineWritten` | When the mirror is gone and a block exists, the log has an exit line. | The block shows `working` forever. |
| `ReportsCommandStatus` | The exit line is the command's status, or 143 after a stop. | The block reports `error` for a command that passed, or the reverse. |
| `NoLostRow` | The session-end list keeps a row for each open block that the mirror listed. | A block whose close failed is never closed. |
| `SettledBlockCloses` | A block whose viewer ended after `done` or `error` is closed, unless its close failed. | Settled blocks pile up in the session. |
| `EndPassClosesSettledRows` | The session-end hook checks each listed row and closes each settled block. | Settled blocks outlive the session. |
| `NeverCloseWorking` | Only a block that shows `done` or `error` is closed. | A running command's block disappears. |
| `WaiterStartedOpenSeesOutcome` | A waiter that starts on an open block gets `done` or `error`. | An agent waits on a mirror block and never learns the result. |
| `LateWaiterSeesOutcome` | A waiter that starts at any time gets `done` or `error`. | The same, for a waiter that starts late. |

## Run it

From the repository root:

```sh
uv run .agents/skills/verify-rex-mirror/scripts/check.py
```

It needs uv and mise. It uses the statechart skill's pinned TLC and Java
through `.github/scripts/statechart_tlc.py`, or `TLA2TOOLS` and `JAVA` when
they are set. It runs the 15 runs in `RUNS` in parallel, in about 10 s.
It exits 0 only when each run gives its expected result:

- `holds`: each listed rule holds on the current code.
- `finding`: a known finding in the current code still breaks its rule.
- `past bug`: the code before a past fix breaks the rule that the fix restored.
- `mutant`: a broken variant breaks a rule that no past bug broke.

For each rule that breaks, it prints TLC's shortest path as a list of
actions. `--keep` keeps the TLC configs and output.

Read every result, and draw the lifecycle, with the `statechart` skill. Give
it `RexMirror.tla`, `chart.cfg`, and the view `chart-view.mjs`. The chart
config has one mirror, no session-end hook, and no waiter, so it stays under
the statechart budget.

## Findings in the current code

Each finding was replayed against the real scripts, one step for each
action. The check keeps each one as a `finding` run, so a fix shows up as a
failing run. When a fix lands, move its run to `holds`.

1. **A stop before the signal handlers leaves the block working forever.**
   `ExitLineWritten`. Path: the mirror creates its log; `startViewer` opens
   the block; Claude Code stops the task while `spawnSync` waits for the
   `rex run` reply. `rex_mirror.ts` sets its handlers only after
   `startViewer` and `remember`, so the default action kills it. No exit
   line is written, the viewer polls forever, and no row exists, so
   `session_end.ts` never sees the block.
2. **`session_end.ts` drops a row that `remember` appends during its pass.**
   `NoLostRow`. It reads the file, checks each row, and then overwrites the
   file with the rows it kept.
3. **A waiter that starts after the close gets "block not found".**
   `LateWaiterSeesOutcome`. The viewer closes its block `CLOSE_DELAY_MS`
   (1 s) after it reports the status. A real Rex run of `wait-status.lua`
   on a closed mirror block printed `block not found` and exited 1. A
   waiter that started before the close printed `error` and the message
   `exit 3`.
4. **A `rex run` reply after the 15 s timeout breaks the close.**
   `SettledBlockCloses` and `WaiterStartedOpenSeesOutcome`. `startViewer`
   returns null, so the mirror deletes the log at the end and lists no
   row. When the viewer already has the log open, it reports the status and
   then crashes in `unlinkSync`, before `closeBlock`. When the viewer opens
   the log after the delete, it crashes in `openSync`, and the block shows
   `working` forever.

## How the model maps to the code

Each action in `RexMirror.tla` is one indivisible step of the real code. The
comment above each action names the file and the function.

- The command and its wrapper: `mirrored` in `hooks/mirror_hook.ts`. The
  subshell ends, `printf` writes the marker, and the pipe closes in one step.
- The mirror: `main`, `startViewer`, `remember`, and `onSignal` in
  `scripts/rex_mirror.ts`.
- The viewer: `main` and `closeBlock` in `scripts/rex_mirror_view.ts`.
- The session-end pass: `main` and `newestState` in `hooks/session_end.ts`,
  one action for each row.
- The waiter: `scripts/wait-status.lua`, its first read and its wait.
- A stop (`Kill`): Claude Code sends SIGTERM to the task's process group.
  The viewer runs under the Rex server, outside that group.

`Variant` selects the current code or a past or broken variant:
`trapWrapper` (before `2a8e0e6`), `noSignalHandlers` and `endPassAborts`
(before `d53f272`), `noViewerClose` and `endPassKeepsError` (before
`9338e63`), and the mutant `closeBeforeStatus`.

### Bounds

One or two mirrors, exit codes 0 and 1 (plus 143 and 125), plain commands
and commands that run `exec` or set an EXIT trap, one session-end pass, and
one waiter on the first mirror. The largest run, two mirrors, has about
290,000 states.

### Assumptions

- In a group stop, the mirror handles its SIGTERM before it reads the end of
  the pipe. Thirty runs of the real wrapper under a process-group SIGTERM
  all ended `error: exit 143`. When the end of the pipe comes first, the
  mirror writes 125, and the model does not show that.
- `rex run` opens the block and starts the viewer in one step.
- Time is not modeled. The 1 s close delay, the 15 s and 10 s timeouts, and
  the viewer's 200 ms poll are only orders of steps.

### Left out

SIGKILL (no handler can run, so it acts like finding 1 at any step), SIGINT
and SIGHUP (the same handler as SIGTERM), the held tail and the nonce check
(unit tests in `plugins/rex-agents/scripts/tests/` cover them), more than one
session, and a Rex server restart.

A failed close in the session-end pass is also left out. `EndChecks` always
closes a settled block, but `session_end.ts` ignores the result of
`rex block close` and drops the row anyway. A replay with a fake `rex` whose
close exits 1 deleted the row and left the block open.

## Coverage

| Code | Actions |
| --- | --- |
| `hooks/mirror_hook.ts` `mirrored` | `CommandEnds` |
| `scripts/rex_mirror.ts` `main`, `startViewer`, `remember`, `onSignal` | `MirrorCreatesLog` to `MirrorHandlesSignal`, `Kill` |
| `scripts/rex_mirror_view.ts` `main`, `closeBlock` | `ViewerReportsWorking` to `ViewerCloseFails` |
| `hooks/session_end.ts` `main`, `newestState` | `EndReads`, `EndChecks`, `EndWrites` |
| `scripts/wait-status.lua` | `WaiterStarts`, `WaiterWakes` |

All paths are under `plugins/rex-agents/`.

Sync commit: `325ba0e`. At that commit the model describes the code. The
covered files last changed in `9338e63`. Move the sync commit forward only
after you confirm that the model describes the code at the new commit.

The check does not run the real code. A change to a covered file passes the
check until someone changes the model to match. So after a change to a
covered file, update the action first, then run the check.

## When the check fails

1. Run the check on the base commit and on your change.
2. A `holds` run that fails: read the path with the `statechart` skill.
   Replay it against the real scripts, one step for each action, with a
   fake `rex` on `PATH` and a scratch `HOME` and `TMPDIR`. When every step
   happens, the change has a bug, or the rule changed on purpose. When a
   step cannot happen in the code, the model is wrong: fix the action, not
   the rule.
3. A `finding` run that fails: the change fixed the finding. Move the run to
   `holds`, and remove the finding from this file.
4. A `past bug` or `mutant` run that fails: the model no longer reaches that
   bug. Check that the variant still matches the old code.
5. An intended change to the lifecycle: change the action first, then rerun.
   Change a rule only when the promise changed, and say why in the same
   change. Never flip an expected result only to make the check pass.
6. "TLC failed": a parse or config error. Read the output that it prints.
