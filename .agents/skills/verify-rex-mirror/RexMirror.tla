---------------------------- MODULE RexMirror ----------------------------
(***************************************************************************)
(* The rex-agents mirror block lifecycle in plugins/rex-agents.            *)
(*                                                                         *)
(* Each action is one indivisible step of the real code. The comment above *)
(* each action names the file and the function. SKILL.md lists the bounds  *)
(* and what the model leaves out.                                          *)
(***************************************************************************)
EXTENDS Integers, FiniteSets

CONSTANTS
  Mirrors,          \* the mirrored background commands of one session
  Codes,            \* the exit codes a command can end with
  Kinds,            \* "plain", or "exec" for a command that runs exec or sets its own EXIT trap
  KillFrom,         \* "start": a kill can reach the mirror at any step; "reading": only after it reads stdin
  DelayZero,        \* TRUE: REX_AGENTS_MIRROR_DELAY_MS=0, so main() opens the block at once
  LayerCanFail,     \* TRUE: Rex can refuse session.new_layer, so the mirror falls back to `rex run`
  ReplyCanTimeOut,  \* TRUE: a reply to session.new_layer or `rex run` can come after its 15 s timeout
  EndOn,            \* TRUE: the SessionEnd hook runs once
  EndFaults,        \* TRUE: its `rex block close` can fail, and Claude Code can kill it mid-pass
  WaiterOn,         \* TRUE: an agent runs wait-status.lua once on a block of Watched
  Watched,
  Variant           \* "fixed" for the current code, or a past or broken variant (SKILL.md)

NONE == -1
NOMARKER == 125    \* rex_mirror.ts NO_MARKER
SIGTERM == 143     \* 128 + 15, written by onSignal
Settled == {"done", "error"}
\* A mirror can open up to two blocks: the floating layer of session.new_layer, and the
\* block of the fallback `rex run`. A block is the pair <<mirror, slot>>.
Slots == {"layer", "run"}

VARIABLES
  kind, cmd, cmdRc, marker,                              \* the command and the wrapper of mirror_hook.mirrored
  mpc, opc, known, killed, sigPending, exitLine, logExists,  \* rex_mirror.ts main() and openViewer()
  req, callDead,                                         \* each open request, and whether its client died
  block, vpc, status, shown, closeFailed,                \* each block and its rex_mirror_view.ts
  rows, fileExists, listed,                              \* the row files ~/.cache/rex-agents/<session_id>.*.json
  spc, snapshot, todo, keep, seen, endCloseFailed,       \* session_end.ts
  wpc, wresult, wOpen, wBlock                            \* wait-status.lua

cmdVars == <<kind, cmd, cmdRc, marker>>
mirrorVars == <<mpc, opc, known, killed, sigPending, exitLine, logExists>>
viewVars == <<block, vpc, status, shown, closeFailed>>
cacheVars == <<rows, fileExists, listed>>
endVars == <<spc, snapshot, todo, keep, seen, endCloseFailed>>
waitVars == <<wpc, wresult, wOpen, wBlock>>
vars == <<cmdVars, mirrorVars, req, callDead, viewVars, cacheVars, endVars, waitVars>>

PerBlock(v) == [m \in Mirrors |-> [k \in Slots |-> v]]

Init ==
  /\ kind \in [Mirrors -> Kinds]
  /\ cmd = [m \in Mirrors |-> "running"]
  /\ cmdRc = [m \in Mirrors |-> NONE]
  /\ marker = [m \in Mirrors |-> NONE]
  /\ mpc = [m \in Mirrors |-> "start"]
  /\ opc = [m \in Mirrors |-> "none"]
  /\ known = [m \in Mirrors |-> "none"]
  /\ killed = [m \in Mirrors |-> FALSE]
  /\ sigPending = [m \in Mirrors |-> FALSE]
  /\ exitLine = [m \in Mirrors |-> NONE]
  /\ logExists = [m \in Mirrors |-> FALSE]
  /\ req = PerBlock("none")
  /\ callDead = [m \in Mirrors |-> FALSE]
  /\ block = PerBlock("none")
  /\ vpc = PerBlock("none")
  /\ status = PerBlock("none")
  /\ shown = PerBlock(NONE)
  /\ closeFailed = PerBlock(FALSE)
  /\ rows = {}
  /\ fileExists = FALSE
  /\ listed = PerBlock(FALSE)
  /\ spc = "idle"
  /\ snapshot = {}
  /\ todo = {}
  /\ keep = {}
  /\ seen = PerBlock("unchecked")
  /\ endCloseFailed = PerBlock(FALSE)
  /\ wpc = "idle"
  /\ wresult = "none"
  /\ wOpen = FALSE
  /\ wBlock = <<Watched, "layer">>

\* Variant "floatAsWritten" is the floating open as first written: main() opened the block
\* at delay 0 before it set its signal handlers; a layer request that died before its reply
\* fell back to `rex run`; and a `rex run` that died before its reply counted as no block.
OpenFirst == Variant = "floatAsWritten"
BlindFallback == Variant = "floatAsWritten"
UnknownIsNoBlock == Variant = "floatAsWritten"

-----------------------------------------------------------------------------
(* The command, in the shell form that mirror_hook.ts mirrored() builds:   *)
(*   { ( :; CMD\n ); printf '\n__rex_rc=%d\n' "$?"; } 2>&1 | rex_mirror.ts *)
(* The subshell ends, printf writes the marker, and the pipe closes. No    *)
(* actor reads between these, so they are one step. Variant "trapWrapper"  *)
(* is the form before 2a8e0e6, { trap 'printf ...' EXIT; CMD\nexit $?; }:  *)
(* exec, or the command's own EXIT trap, skips the marker.                 *)

CommandEnds(m, rc) ==
  /\ cmd[m] = "running"
  /\ cmd' = [cmd EXCEPT ![m] = "exited"]
  /\ cmdRc' = [cmdRc EXCEPT ![m] = rc]
  /\ marker' = [marker EXCEPT ![m] =
                  IF Variant = "trapWrapper" /\ kind[m] = "exec" THEN NONE ELSE rc]
  /\ UNCHANGED <<kind, mirrorVars, req, callDead, viewVars, cacheVars, endVars, waitVars>>

(* Claude Code stops the background task: SIGTERM to its process group.    *)
(* A running command dies before printf, so the pipe closes with no        *)
(* marker. The mirror's default action kills it at once, unless main() has *)
(* run process.on("SIGTERM", ...): then the signal waits for the event     *)
(* loop. A `rex` client that the mirror waits on is in the group too, so   *)
(* it dies before its reply (callDead, then MirrorLayerGivesUp or          *)
(* MirrorRunGivesUp); a client started after the stop does not. The        *)
(* viewers run under the Rex server, outside the group.                    *)

HandlersOn(m) == mpc[m] \in {"armed", "reading"} /\ Variant # "noSignalHandlers"

Kill(m) ==
  /\ ~killed[m]
  /\ mpc[m] \notin {"ended", "dead"}
  /\ KillFrom = "reading" => mpc[m] = "reading"
  /\ killed' = [killed EXCEPT ![m] = TRUE]
  /\ IF cmd[m] = "running"
       THEN /\ cmd' = [cmd EXCEPT ![m] = "killed"]
            /\ cmdRc' = [cmdRc EXCEPT ![m] = SIGTERM]
       ELSE UNCHANGED <<cmd, cmdRc>>
  /\ IF HandlersOn(m)
       THEN /\ sigPending' = [sigPending EXCEPT ![m] = TRUE]
            /\ UNCHANGED mpc
       ELSE /\ mpc' = [mpc EXCEPT ![m] = "dead"]
            /\ UNCHANGED sigPending
  /\ callDead' = [callDead EXCEPT ![m] = @ \/ opc[m] \in {"layer", "run"}]
  /\ UNCHANGED <<kind, marker, opc, known, exitLine, logExists,
                 req, viewVars, cacheVars, endVars, waitVars>>

-----------------------------------------------------------------------------
(* rex_mirror.ts main(). mpc: "start", "log" (log created), "armed"        *)
(* (handlers set, main() still running), "reading" (in the for-await       *)
(* loop), "ended", or "dead". opc follows openViewer: "none", "timer" (the *)
(* delay is pending), "inspect", "layer", "minimize", "run" (a `rex` call  *)
(* in flight), then "opened", "listed", "noBlock", "unknown", or           *)
(* "cancelled".                                                            *)

\* "opened": startViewer returned, and openViewer still has to call remember.
Opening(m) == opc[m] \in {"inspect", "layer", "minimize", "run", "opened"}

Alive(m) == mpc[m] \notin {"dead", "ended"}

\* writeFileSync(log, "", { flag: "wx" }) and openSync(log, "a").
MirrorCreatesLog(m) ==
  /\ mpc[m] = "start"
  /\ mpc' = [mpc EXCEPT ![m] = "log"]
  /\ opc' = [opc EXCEPT ![m] = IF DelayZero /\ OpenFirst THEN "inspect" ELSE "none"]
  /\ logExists' = [logExists EXCEPT ![m] = TRUE]
  /\ UNCHANGED <<cmdVars, known, killed, sigPending, exitLine,
                 req, callDead, viewVars, cacheVars, endVars, waitVars>>

\* The three process.on(...) calls. At a delay above 0, setTimeout(openViewer, delay).
\* OpenFirst: at delay 0 the open already ran, before the handlers.
MirrorInstallsHandlers(m) ==
  /\ mpc[m] = "log"
  /\ ~Opening(m)
  /\ mpc' = [mpc EXCEPT ![m] = IF DelayZero /\ ~OpenFirst THEN "armed" ELSE "reading"]
  /\ opc' = [opc EXCEPT ![m] =
               IF ~DelayZero THEN "timer"
               ELSE IF OpenFirst THEN @
               ELSE "inspect"]
  /\ UNCHANGED <<cmdVars, known, killed, sigPending, exitLine, logExists,
                 req, callDead, viewVars, cacheVars, endVars, waitVars>>

\* At delay 0, the synchronous openViewer() has returned, and main() enters the loop.
MirrorStartsReading(m) ==
  /\ mpc[m] = "armed"
  /\ ~Opening(m)
  /\ mpc' = [mpc EXCEPT ![m] = "reading"]
  /\ UNCHANGED <<cmdVars, opc, known, killed, sigPending, exitLine, logExists,
                 req, callDead, viewVars, cacheVars, endVars, waitVars>>

\* The delay timer fires in the event loop, and openViewer() starts. It runs to its end
\* with no await, so no signal handler and no read of stdin runs until it returns.
MirrorTimerFires(m) ==
  /\ mpc[m] = "reading"
  /\ opc[m] = "timer"
  /\ opc' = [opc EXCEPT ![m] = "inspect"]
  /\ UNCHANGED <<cmdVars, mpc, known, killed, sigPending, exitLine, logExists,
                 req, callDead, viewVars, cacheVars, endVars, waitVars>>

\* startViewer: windowForBlock runs `rex block inspect` (5 s timeout; its result only picks
\* the window). Then spawnSync(`rex api call session.new_layer`) sends the request.
MirrorInspects(m) ==
  /\ Alive(m)
  /\ opc[m] = "inspect"
  /\ opc' = [opc EXCEPT ![m] = "layer"]
  /\ req' = [req EXCEPT ![m]["layer"] = "sent"]
  /\ callDead' = [callDead EXCEPT ![m] = FALSE]
  /\ UNCHANGED <<cmdVars, mpc, known, killed, sigPending, exitLine, logExists,
                 viewVars, cacheVars, endVars, waitVars>>

\* startViewer: new_layer replies with layer_id and block_ids.
MirrorGetsLayer(m) ==
  /\ Alive(m)
  /\ opc[m] = "layer"
  /\ req[m]["layer"] = "opened"
  /\ opc' = [opc EXCEPT ![m] = "minimize"]
  /\ known' = [known EXCEPT ![m] = "layer"]
  /\ UNCHANGED <<cmdVars, mpc, killed, sigPending, exitLine, logExists,
                 req, callDead, viewVars, cacheVars, endVars, waitVars>>

\* startViewer: new_layer exits non-zero, so the mirror falls back to `rex run`.
MirrorLayerRefused(m) ==
  /\ Alive(m)
  /\ opc[m] = "layer"
  /\ req[m]["layer"] = "refused"
  /\ opc' = [opc EXCEPT ![m] = "run"]
  /\ req' = [req EXCEPT ![m]["run"] = "sent"]
  /\ callDead' = [callDead EXCEPT ![m] = FALSE]
  /\ UNCHANGED <<cmdVars, mpc, known, killed, sigPending, exitLine, logExists,
                 viewVars, cacheVars, endVars, waitVars>>

\* startViewer: diedBeforeReply(layer), at the 15 s timeout or in a group stop. Rex may still
\* open the layer, so startViewer returns "unknown" and opens no fallback. BlindFallback: the
\* mirror falls back to `rex run`.
MirrorLayerGivesUp(m) ==
  /\ Alive(m)
  /\ opc[m] = "layer"
  /\ ReplyCanTimeOut \/ callDead[m]
  /\ req[m]["layer"] \in {"sent", "opened"}
  /\ callDead' = [callDead EXCEPT ![m] = FALSE]
  /\ IF BlindFallback
       THEN /\ opc' = [opc EXCEPT ![m] = "run"]
            /\ req' = [req EXCEPT ![m]["run"] = "sent"]
       ELSE /\ opc' = [opc EXCEPT ![m] = "unknown"]
            /\ UNCHANGED req
  /\ UNCHANGED <<cmdVars, mpc, known, killed, sigPending, exitLine, logExists,
                 viewVars, cacheVars, endVars, waitVars>>

\* startViewer: `rex api call session.set_layer_state` (5 s timeout; its result is
\* ignored), and startViewer returns the layer's block ID.
MirrorMinimizes(m) ==
  /\ Alive(m)
  /\ opc[m] = "minimize"
  /\ opc' = [opc EXCEPT ![m] = "opened"]
  /\ UNCHANGED <<cmdVars, mpc, known, killed, sigPending, exitLine, logExists,
                 req, callDead, viewVars, cacheVars, endVars, waitVars>>

\* startViewer: `rex run` replies with block_ids.
MirrorGetsRun(m) ==
  /\ Alive(m)
  /\ opc[m] = "run"
  /\ req[m]["run"] = "opened"
  /\ opc' = [opc EXCEPT ![m] = "opened"]
  /\ known' = [known EXCEPT ![m] = "run"]
  /\ UNCHANGED <<cmdVars, mpc, killed, sigPending, exitLine, logExists,
                 req, callDead, viewVars, cacheVars, endVars, waitVars>>

\* startViewer: `rex run` exits non-zero before it opens a block, and returns null.
MirrorRunRefused(m) ==
  /\ Alive(m)
  /\ opc[m] = "run"
  /\ req[m]["run"] = "refused"
  /\ opc' = [opc EXCEPT ![m] = "noBlock"]
  /\ UNCHANGED <<cmdVars, mpc, known, killed, sigPending, exitLine, logExists,
                 req, callDead, viewVars, cacheVars, endVars, waitVars>>

\* startViewer: diedBeforeReply(r) for `rex run`. Rex may still open the block, so
\* startViewer returns "unknown". UnknownIsNoBlock: it returns null, as if no block opened.
MirrorRunGivesUp(m) ==
  /\ Alive(m)
  /\ opc[m] = "run"
  /\ ReplyCanTimeOut \/ callDead[m]
  /\ req[m]["run"] \in {"sent", "opened"}
  /\ opc' = [opc EXCEPT ![m] = IF UnknownIsNoBlock THEN "noBlock" ELSE "unknown"]
  /\ UNCHANGED <<cmdVars, mpc, known, killed, sigPending, exitLine, logExists,
                 req, callDead, viewVars, cacheVars, endVars, waitVars>>

\* openViewer: remember writes one row file, then viewer = { kind: "open" }.
MirrorRemembers(m) ==
  /\ Alive(m)
  /\ opc[m] = "opened"
  /\ opc' = [opc EXCEPT ![m] = "listed"]
  /\ rows' = rows \cup {<<m, known[m]>>}
  /\ fileExists' = TRUE
  /\ listed' = [listed EXCEPT ![m][known[m]] = TRUE]
  /\ UNCHANGED <<cmdVars, mpc, known, killed, sigPending, exitLine, logExists,
                 req, callDead, viewVars, endVars, waitVars>>

\* settleLog(code). An open viewer, or one that may have opened ("unknown"): write the exit
\* line and keep the log, which the viewer deletes. A pending timer: clear it. Otherwise:
\* delete the log with no exit line.
Settle(m, code) ==
  /\ IF opc[m] \in {"listed", "unknown"}
       THEN /\ exitLine' = [exitLine EXCEPT ![m] = code]
            /\ UNCHANGED <<logExists, opc>>
       ELSE /\ logExists' = [logExists EXCEPT ![m] = FALSE]
            /\ opc' = [opc EXCEPT ![m] = IF @ = "timer" THEN "cancelled" ELSE @]
            /\ UNCHANGED exitLine
  /\ mpc' = [mpc EXCEPT ![m] = "ended"]

\* The `for await` loop sees end of input, and main() yields once (setImmediate). The rest
\* of main() and process.exit run with no await between them, so no signal handler can run
\* in between. A pending signal is handled first (SKILL.md, "Assumptions").
MirrorReadsEnd(m) ==
  /\ mpc[m] = "reading"
  /\ ~Opening(m)
  /\ cmd[m] # "running"
  /\ ~sigPending[m]
  /\ Settle(m, IF marker[m] # NONE THEN marker[m] ELSE NOMARKER)
  /\ UNCHANGED <<cmdVars, known, killed, sigPending, req, callDead, viewVars, cacheVars, endVars, waitVars>>

\* onSignal(143)
MirrorHandlesSignal(m) ==
  /\ mpc[m] = "reading"
  /\ ~Opening(m)
  /\ sigPending[m]
  /\ Settle(m, SIGTERM)
  /\ UNCHANGED <<cmdVars, known, killed, sigPending, req, callDead, viewVars, cacheVars, endVars, waitVars>>

-----------------------------------------------------------------------------
(* The Rex server. It handles a request whether or not its client still    *)
(* waits for the reply.                                                    *)

\* The server opens the block and starts its viewer.
ServerOpens(m, k) ==
  /\ req[m][k] = "sent"
  /\ req' = [req EXCEPT ![m][k] = "opened"]
  /\ block' = [block EXCEPT ![m][k] = "open"]
  /\ vpc' = [vpc EXCEPT ![m][k] = "started"]
  /\ UNCHANGED <<cmdVars, mirrorVars, callDead, status, shown, closeFailed, cacheVars, endVars, waitVars>>

\* The server refuses the request and opens no block.
ServerRefuses(m, k) ==
  /\ req[m][k] = "sent"
  /\ k = "layer" => LayerCanFail
  /\ req' = [req EXCEPT ![m][k] = "refused"]
  /\ UNCHANGED <<cmdVars, mirrorVars, callDead, viewVars, cacheVars, endVars, waitVars>>

-----------------------------------------------------------------------------
(* rex_mirror_view.ts main(), in each block. A close of the block ends it. *)

Close(m, k) ==
  /\ block' = [block EXCEPT ![m][k] = "closed"]
  /\ vpc' = [vpc EXCEPT ![m][k] = IF @ = "closing" THEN "ended" ELSE @]

\* status("working", label), and the header line.
ViewerReportsWorking(m, k) ==
  /\ vpc[m][k] = "started"
  /\ vpc' = [vpc EXCEPT ![m][k] = "working"]
  /\ status' = [status EXCEPT ![m][k] = "working"]
  /\ UNCHANGED <<cmdVars, mirrorVars, req, callDead, block, shown, closeFailed, cacheVars, endVars, waitVars>>

\* openSync(log, "r"): throws, and the viewer exits, when the log is gone.
ViewerOpensLog(m, k) ==
  /\ vpc[m][k] = "working"
  /\ vpc' = [vpc EXCEPT ![m][k] = IF logExists[m] THEN "reading" ELSE "crashed"]
  /\ UNCHANGED <<cmdVars, mirrorVars, req, callDead, block, status, shown, closeFailed,
                 cacheVars, endVars, waitVars>>

\* The read loop finds the exit line: status(done or error), closeSync, unlinkSync(log).
\* unlinkSync throws when the log is already gone, and the viewer exits. A viewer whose
\* log was deleted with no exit line polls forever.
\* Variant "noViewerClose" is the viewer before 9338e63: it returns here.
\* Variant "closeBeforeStatus" is a broken viewer that closes the block first.
ViewerReadsExitLine(m, k) ==
  /\ vpc[m][k] = "reading"
  /\ exitLine[m] # NONE
  /\ IF Variant = "closeBeforeStatus"
       THEN /\ block' = [block EXCEPT ![m][k] = "closed"]
            /\ vpc' = [vpc EXCEPT ![m][k] = "ended"]
            /\ UNCHANGED <<status, shown, logExists>>
       ELSE /\ status' = [status EXCEPT ![m][k] = IF exitLine[m] = 0 THEN "done" ELSE "error"]
            /\ shown' = [shown EXCEPT ![m][k] = exitLine[m]]
            /\ logExists' = [logExists EXCEPT ![m] = FALSE]
            /\ vpc' = [vpc EXCEPT ![m][k] =
                         IF ~logExists[m] THEN "crashed"
                         ELSE IF Variant = "noViewerClose" THEN "ended"
                         ELSE "closing"]
            /\ UNCHANGED block
  /\ UNCHANGED <<cmdVars, mpc, opc, known, killed, sigPending, exitLine,
                 req, callDead, closeFailed, cacheVars, endVars, waitVars>>

\* After CLOSE_DELAY_MS, closeBlock: `rex block close` succeeds.
ViewerClosesBlock(m, k) ==
  /\ vpc[m][k] = "closing"
  /\ Close(m, k)
  /\ UNCHANGED <<cmdVars, mirrorVars, req, callDead, status, shown, closeFailed, cacheVars, endVars, waitVars>>

\* After CLOSE_DELAY_MS, closeBlock: `rex block close` fails or times out; main() returns.
ViewerCloseFails(m, k) ==
  /\ vpc[m][k] = "closing"
  /\ vpc' = [vpc EXCEPT ![m][k] = "ended"]
  /\ closeFailed' = [closeFailed EXCEPT ![m][k] = TRUE]
  /\ UNCHANGED <<cmdVars, mirrorVars, req, callDead, block, status, shown, cacheVars, endVars, waitVars>>

-----------------------------------------------------------------------------
(* session_end.ts main(), once. The current hook reads one row file per   *)
(* block and deletes a row file only after its block's close succeeded or  *)
(* the block is gone. Rewrites is the hook before the per-row list, and    *)
(* before d53f272 and 9338e63: it read one shared list, kept rows in       *)
(* `keep`, and rewrote the list at the end.                                *)

Rewrites == Variant \in {"endPassRewrites", "endPassAborts", "endPassKeepsError"}

\* rowFiles: readdirSync and a read of each row file. Rewrites: existsSync(path), readFileSync(path).
EndReads ==
  /\ EndOn
  /\ spc = "idle"
  /\ IF fileExists
       THEN /\ spc' = "checking"
            /\ snapshot' = rows
            /\ todo' = rows
       ELSE /\ spc' = "finished"
            /\ UNCHANGED <<snapshot, todo>>
  /\ UNCHANGED <<keep, seen, endCloseFailed, cmdVars, mirrorVars, req, callDead, viewVars, cacheVars, waitVars>>

\* What newestState returns: "gone" for a closed block; for an open one, the newest
\* record's state ("null" when none), or "fail" for a rex timeout or non-JSON reply.
Answers(m, k) ==
  IF block[m][k] = "closed" THEN {"gone"}
  ELSE {IF status[m][k] = "none" THEN "null" ELSE status[m][k], "fail"}

Closes == IF Variant = "endPassKeepsError" THEN {"done"} ELSE Settled

\* settle for one row: newestState, then `rex block close` and unlinkSync(file) for a settled
\* block, unlinkSync(file) for a gone one, or nothing. Rewrites: close, or keep.push.
\* Variant "endPassKeepsError" is the hook before 9338e63. Variant "endPassAborts" is the
\* hook before d53f272: an unreadable reply throws, and the hook exits without a write.
EndChecks(m, k) ==
  /\ spc = "checking"
  /\ <<m, k>> \in todo
  /\ \E a \in Answers(m, k):
       /\ seen' = [seen EXCEPT ![m][k] = a]
       /\ todo' = todo \ {<<m, k>>}
       /\ IF a = "fail" /\ Variant = "endPassAborts"
            THEN /\ spc' = "aborted"
                 /\ UNCHANGED <<keep, block, vpc, rows>>
            ELSE IF a \in Closes
            THEN /\ Close(m, k)
                 /\ rows' = IF Rewrites THEN rows ELSE rows \ {<<m, k>>}
                 /\ UNCHANGED <<spc, keep>>
            ELSE /\ keep' = IF a = "gone" THEN keep ELSE keep \cup {<<m, k>>}
                 /\ rows' = IF ~Rewrites /\ a = "gone" THEN rows \ {<<m, k>>} ELSE rows
                 /\ UNCHANGED <<spc, block, vpc>>
  /\ UNCHANGED <<snapshot, endCloseFailed, cmdVars, mirrorVars, req, callDead, status, shown, closeFailed,
                 fileExists, listed, waitVars>>

\* settle for one row: newestState answers done or error, and `rex block close` fails or
\* times out. The hook keeps the row file. Rewrites ignores the result and drops the row.
EndCloseFails(m, k) ==
  /\ EndFaults
  /\ spc = "checking"
  /\ <<m, k>> \in todo
  /\ \E a \in Answers(m, k) \cap Closes :
       /\ seen' = [seen EXCEPT ![m][k] = a]
       /\ todo' = todo \ {<<m, k>>}
       /\ endCloseFailed' = [endCloseFailed EXCEPT ![m][k] = TRUE]
  /\ UNCHANGED <<spc, snapshot, keep, cmdVars, mirrorVars, req, callDead, viewVars, cacheVars, waitVars>>

\* Claude Code kills the hook mid-pass, at its 30 s timeout.
EndKilled ==
  /\ EndFaults
  /\ spc = "checking"
  /\ spc' = "killed"
  /\ UNCHANGED <<snapshot, todo, keep, seen, endCloseFailed, cmdVars, mirrorVars, req, callDead, viewVars,
                 cacheVars, waitVars>>

\* The loop ends. Rewrites: writeFileSync(path, keep) or unlinkSync(path), which loses the
\* rows appended since EndReads.
EndWrites ==
  /\ spc = "checking"
  /\ todo = {}
  /\ spc' = "finished"
  /\ IF Rewrites
       THEN /\ rows' = keep
            /\ fileExists' = (keep # {})
       ELSE UNCHANGED <<rows, fileExists>>
  /\ UNCHANGED <<listed, snapshot, todo, keep, seen, endCloseFailed, cmdVars, mirrorVars, req, callDead,
                 viewVars, waitVars>>

-----------------------------------------------------------------------------
(* wait-status.lua on a block of Watched, once. Events buffer from the     *)
(* start of the script, so the first read and the wait miss nothing.       *)

\* rex.block.call(program_status), then rex.block.call(process).
WaiterStarts ==
  /\ WaiterOn
  /\ wpc = "idle"
  /\ \E k \in Slots :
       /\ block[Watched][k] # "none"
       /\ wBlock' = <<Watched, k>>
       /\ wOpen' = (block[Watched][k] = "open")
       /\ IF block[Watched][k] = "closed"
            THEN /\ wpc' = "done"
                 /\ wresult' = "not found"
            ELSE IF status[Watched][k] \in Settled
            THEN /\ wpc' = "done"
                 /\ wresult' = status[Watched][k]
            ELSE IF vpc[Watched][k] = "crashed"
            THEN /\ wpc' = "done"
                 /\ wresult' = "viewer exit"
            ELSE /\ wpc' = "waiting"
                 /\ UNCHANGED wresult
  /\ UNCHANGED <<cmdVars, mirrorVars, req, callDead, viewVars, cacheVars, endVars>>

\* rex.wait returns on program_status_changed (settled) or on child_exited.
WaiterWakes ==
  /\ wpc = "waiting"
  /\ LET m == wBlock[1]
         k == wBlock[2]
     IN \/ /\ status[m][k] \in Settled
           /\ wresult' = status[m][k]
        \/ /\ status[m][k] \notin Settled
           /\ vpc[m][k] = "crashed" \/ block[m][k] = "closed"
           /\ wresult' = "viewer exit"
  /\ wpc' = "done"
  /\ UNCHANGED <<wOpen, wBlock, cmdVars, mirrorVars, req, callDead, viewVars, cacheVars, endVars>>

-----------------------------------------------------------------------------

Next ==
  \/ \E m \in Mirrors, rc \in Codes : CommandEnds(m, rc)
  \/ \E m \in Mirrors :
       \/ Kill(m)
       \/ MirrorCreatesLog(m)
       \/ MirrorInstallsHandlers(m)
       \/ MirrorStartsReading(m)
       \/ MirrorTimerFires(m)
       \/ MirrorInspects(m)
       \/ MirrorGetsLayer(m)
       \/ MirrorLayerRefused(m)
       \/ MirrorLayerGivesUp(m)
       \/ MirrorMinimizes(m)
       \/ MirrorGetsRun(m)
       \/ MirrorRunRefused(m)
       \/ MirrorRunGivesUp(m)
       \/ MirrorRemembers(m)
       \/ MirrorReadsEnd(m)
       \/ MirrorHandlesSignal(m)
  \/ \E m \in Mirrors, k \in Slots :
       \/ ServerOpens(m, k)
       \/ ServerRefuses(m, k)
       \/ ViewerReportsWorking(m, k)
       \/ ViewerOpensLog(m, k)
       \/ ViewerReadsExitLine(m, k)
       \/ ViewerClosesBlock(m, k)
       \/ ViewerCloseFails(m, k)
       \/ EndChecks(m, k)
       \/ EndCloseFails(m, k)
  \/ EndReads
  \/ EndWrites
  \/ EndKilled
  \/ WaiterStarts
  \/ WaiterWakes

Spec == Init /\ [][Next]_vars

-----------------------------------------------------------------------------
(* The rules. SKILL.md gives each one a plain sentence and its harm.       *)

ExitLineWritten ==
  \A m \in Mirrors :
    mpc[m] \in {"ended", "dead"} /\ (\E k \in Slots : block[m][k] # "none") => exitLine[m] # NONE

ReportsCommandStatus ==
  \A m \in Mirrors : exitLine[m] # NONE =>
    \/ exitLine[m] = cmdRc[m]
    \/ killed[m] /\ exitLine[m] = SIGTERM

OneBlockPerMirror ==
  \A m \in Mirrors : Cardinality({k \in Slots : block[m][k] # "none"}) <= 1

NoLostRow ==
  \A m \in Mirrors, k \in Slots : listed[m][k] /\ block[m][k] = "open" => <<m, k>> \in rows

SettledBlockCloses ==
  \A m \in Mirrors, k \in Slots :
    status[m][k] \in Settled /\ vpc[m][k] \in {"ended", "crashed"} /\ block[m][k] = "open"
      => closeFailed[m][k]

EndPassClosesSettledRows ==
  spc \in {"finished", "aborted"} =>
    \A b \in snapshot :
      LET m == b[1]
          k == b[2]
      IN seen[m][k] # "unchecked"
         /\ (seen[m][k] \in Settled => block[m][k] = "closed" \/ endCloseFailed[m][k])

NeverCloseWorking ==
  \A m \in Mirrors, k \in Slots : block[m][k] = "closed" => status[m][k] \in Settled

WaiterStartedOpenSeesOutcome ==
  wpc = "done" /\ wOpen => wresult \in Settled

LateWaiterSeesOutcome ==
  wpc = "done" => wresult \in Settled

=============================================================================
