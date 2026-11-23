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
`rex_mirror.ts`. After a delay (1.5 s by default), the mirror opens a
minimized floating Rex pane, or falls back to a `rex run` block. The block's
viewer shows `working`, then `done` or `error` with the exit code, and then
closes the block.

The promise: every mirrored block reaches `done` or `error` with the
command's own exit code, then closes, and a working block is never closed.

## The rules

`RexMirror.tla` checks each rule in every state that the steps can reach.

| Rule | Plain sentence | Harm when it breaks |
| --- | --- | --- |
| `ExitLineWritten` | When the mirror is gone and a block exists, the log has an exit line. | The block shows `working` forever. |
| `ReportsCommandStatus` | The exit line is the command's status, or 143 after a stop. | The block reports `error` for a command that passed, or the reverse. |
| `OneBlockPerMirror` | A mirror opens at most one block. | A second pane for the same command; one of the two viewers crashes. |
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
they are set. It runs the 19 runs in `RUNS` in parallel, in about 45 s.
It exits 0 only when each run gives its expected result:

- `holds`: each listed rule holds on the current code.
- `finding`: a known finding in the current code still breaks its rule.
- `past bug`: the code before a past fix breaks the rule that the fix restored.
- `mutant`: a broken variant breaks a rule that no past bug broke.

For each rule that breaks, it prints TLC's shortest path as a list of
actions. `--keep` keeps the TLC configs and output.

Read every result, and draw the lifecycle, with the `statechart` skill. Give
it `RexMirror.tla`, `chart.cfg`, and the view `chart-view.mjs`. The chart
config has one mirror, the default delay, no refused layer, no session-end
hook, and no waiter, so it stays under the statechart budget (227 states).
The check also runs `chart.cfg` as a run, so a constant that the chart config
leaves out fails the check. `chart.mmd` and `report.md` are the skill's output
for `chart.cfg`: 10 states and 11 arrows. After a change to the model or the
view, draw the chart again and replace both files.

## Findings in the current code

Each finding was replayed against the real scripts, one step for each
action. The check keeps each one as a `finding` run, so a fix shows up as a
failing run. When a fix lands, move its run to `holds`.

- **A waiter that starts after the close gets "block not found".**
  `LateWaiterSeesOutcome`. The viewer closes its block `STATUS_GRACE_MS`
  (1 s) after it reports the status. A real Rex run of `wait-status.lua`
  on a closed mirror block printed `block not found` and exited 1. A
  waiter that started before the close printed `error` and the message
  `exit 3`. The `using-rex` skill says so: start the wait before the
  command ends.

## How the model maps to the code

Each action in `RexMirror.tla` is one indivisible step of the real code. The
comment above each action names the file and the function.

- The command and its wrapper: `mirrored` in `hooks/mirror_hook.ts`. The
  subshell ends, `printf` writes the marker, and the pipe closes in one step.
- The mirror: `main`, `withSignalHandlers`, `openViewer`, `startViewer`,
  `remember`, `settleLog`, and `onSignal` in `scripts/rex_mirror.ts`. `mpc` follows `main`: the log,
  the handlers, and the read loop. `opc` follows the open: the delay timer
  (or none at delay 0), `rex block inspect`, `session.new_layer`,
  `session.set_layer_state`, and the fallback `rex run`, each one step.
- The Rex server (`ServerOpens`, `ServerRefuses`): it opens a block, or
  refuses, whether or not the `rex` client still waits for the reply. So a
  mirror has two block slots, `layer` and `run`, and a late reply can open
  a block that the mirror never learns of.
- The viewer: `main` and `closeBlock` in `scripts/rex_mirror_view.ts`.
- The session-end pass: `main`, `rowFiles`, `settle`, and `newestState` in
  `hooks/session_end.ts`, one action for each row. `EndCloseFails` is a
  `rex block close` that fails or times out, and `EndKilled` is Claude Code
  killing the hook at its 30 s timeout. The constant `EndFaults` turns both
  on.
- The waiter: `scripts/wait-status.lua`, its first read and its wait.
- A stop (`Kill`): Claude Code sends SIGTERM to the task's process group.
  A `rex` call in flight is in that group, so its client dies before its
  reply (`callDead`); a client started later does not. The viewer runs under
  the Rex server, outside that group.

`Variant` selects the current code or a past or broken variant:
`trapWrapper` (before `2a8e0e6`), `noSignalHandlers` and `endPassAborts`
(before `d53f272`), `noViewerClose` and `endPassKeepsError` (before
`9338e63`), `endPassRewrites` (before the per-row session-end list),
`floatAsWritten` (the floating open as first written), `rowNotAtomic`
(`remember` before KP-678), and the mutant `closeBeforeStatus`.

`floatAsWritten` opened the block at delay 0 before it set the signal
handlers, so a stop during the open left the block `working`. When the
`session.new_layer` client died before its reply, it fell back to
`rex run`, and a late layer then opened a second block on the same log.
When the `rex run` client died, it counted no block, and deleted the log
with no exit line. The current code sets the handlers first: only `withSignalHandlers`
returns the open, so a call before the handlers fails the type check. A client that
dies (a signal, its timeout, or an exit status of 128 or more) makes the
open `maybeOpen`: no fallback, the exit line is written, and the log stays
for a viewer that may open.

`endPassRewrites` is the hook that kept every row in one shared
`<session_id>.jsonl` file. It read the file, checked each row, and then
overwrote the file with the rows it kept. So it lost a row that `remember`
appended during the pass, and it dropped the row of a block whose close
failed. The `endPassAborts` and `endPassKeepsError` variants rewrite the
same way.

### Bounds

One or two mirrors, exit codes 0 and 1 (plus 143 and 125), plain commands
and commands that run `exec` or set an EXIT trap, one session-end pass, and
one waiter on the first mirror. The two-mirror run uses delay 0 and no
refused layer, and has about 1,200,000 states; with a timer and a fallback
for each mirror it passes 10 million states.

### Assumptions

- In a group stop, the mirror handles its SIGTERM before it reads the end of
  the pipe. Thirty runs of the real wrapper under a process-group SIGTERM
  all ended `error: exit 143`. When the end of the pipe comes first, the
  mirror writes 125, and the model does not show that. A stop during a
  timer-fired open leaves both pending; on node 22.18 the end of input came
  first in 10 of 10 replays, until `main` yielded once (`setImmediate`)
  before it settles. With the yield, 10 of 10 on node and on bun ended 143.
- Rex opens a block and starts its viewer in one step.
- A `rex` client that exits non-zero below 128 opened nothing, so the
  fallback cannot open a second block. A client killed by a signal or its
  timeout exits by the signal or with 128 or more.
- A session-end close that fails leaves the block open. A close that times
  out after Rex closed the block keeps a row for a closed block, which the
  next pass drops as gone, so the model leaves that case out.
- Time is not modeled. The open delay, the 1 s close delay, the 5 s, 10 s,
  and 15 s timeouts, and the viewer's 200 ms poll are only orders of steps.

### Left out

SIGKILL (no handler can run, so it acts like the stop before the handlers,
at any step), SIGINT and SIGHUP (the same handler as SIGTERM), the held tail
and the nonce check (unit tests in `plugins/rex-agents/scripts/tests/` cover
them), more than one session, and a Rex server restart.

Before its pass, the hook turns each line of an old shared
`<session_id>.jsonl` into a row file named by the line's hash, written to a
temp file and renamed so it is complete or absent, then deletes the old file
(`drainLegacyList`). Unit tests cover it, including a rerun after a kill
before the delete and an empty row file left by a kill; the model starts
with no old file.

A reply to `new_layer` or `rex run` that exits 0 but cannot be read counts
as `maybeOpen`, like a dead client; the model does not have that reply. When
the open is `maybeOpen` and no block ever opens, the log stays in `TMPDIR`.

`remember` writes its row to a temp file and renames it, so the row file is
complete or absent. The temp name starts with `.`, so `drainLegacyList`,
which deletes this session's `*.json.tmp.*` files, never deletes it.
`rowNotAtomic` is the code before: `writeFileSync` with `wx` created the row
file empty and then wrote it. A reader that ran beside 50,000 such writes
found an empty row 141 to 240 times per run. A pass that reads an empty row
keeps the file and never checks its block, which breaks
`EndPassClosesSettledRows`.

## Coverage

| Code | Actions |
| --- | --- |
| `hooks/mirror_hook.ts` `mirrored` | `CommandEnds` |
| `scripts/rex_mirror.ts` `main`, `withSignalHandlers`, `openViewer`, `startViewer`, `diedBeforeReply`, `remember`, `settleLog`, `onSignal` | `MirrorCreatesLog` to `MirrorHandlesSignal`, `Kill` |
| The Rex server's side of `new_layer` and `rex run` | `ServerOpens`, `ServerRefuses` |
| `scripts/rex_mirror_view.ts` `main`, `closeBlock` | `ViewerReportsWorking` to `ViewerCloseFails` |
| `hooks/session_end.ts` `main`, `rowFiles`, `settle`, `newestState` (`drainLegacyList` is left out) | `EndReads`, `EndChecks`, `EndCloseFails`, `EndKilled`, `EndWrites` |
| `scripts/wait-status.lua` | `WaiterStarts`, `WaiterWakes` |

All paths are under `plugins/rex-agents/`.

Sync commit: the commit that makes `remember` write its row atomically
(`git log -S rowNotAtomic`). At that commit the model describes the code.
`scripts/rex_mirror.ts` and `hooks/session_end.ts` last changed there; the
other covered files changed in earlier commits. Move the sync commit forward only
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
