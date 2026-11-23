---------------------------- MODULE RexMirror ----------------------------
(***************************************************************************)
(* The rex-agents mirror block lifecycle in plugins/rex-agents.            *)
(*                                                                         *)
(* Each action is one indivisible step of the real code. The comment above *)
(* each action names the file and the function. SKILL.md lists the bounds  *)
(* and what the model leaves out.                                          *)
(***************************************************************************)
EXTENDS Integers

CONSTANTS
  Mirrors,          \* the mirrored background commands of one session
  Codes,            \* the exit codes a command can end with
  Kinds,            \* "plain", or "exec" for a command that runs exec or sets its own EXIT trap
  KillFrom,         \* "start": a kill can reach the mirror at any step; "reading": only after it reads stdin
  ReplyCanTimeOut,  \* TRUE: the reply to `rex run` can come after the 15 s timeout
  EndOn,            \* TRUE: the SessionEnd hook runs once
  WaiterOn,         \* TRUE: an agent runs wait-status.lua once on the block of Watched
  Watched,
  Variant           \* "fixed" for the current code, or a past or broken variant (SKILL.md)

NONE == -1
NOMARKER == 125    \* rex_mirror.ts NO_MARKER
SIGTERM == 143     \* 128 + 15, written by onSignal
Settled == {"done", "error"}

VARIABLES
  kind, cmd, cmdRc, marker,                                  \* the command and the wrapper of mirror_hook.mirrored
  mpc, killed, sigPending, blockKnown, listed, exitLine, logExists,  \* rex_mirror.ts
  block, vpc, status, shown, closeFailed,                    \* the Rex block and rex_mirror_view.ts
  rows, fileExists,                                          \* ~/.cache/rex-agents/<session_id>.jsonl
  spc, snapshot, todo, keep, seen,                           \* session_end.ts
  wpc, wresult, wOpen                                        \* wait-status.lua

cmdVars == <<kind, cmd, cmdRc, marker>>
mirrorVars == <<mpc, killed, sigPending, blockKnown, listed, exitLine, logExists>>
viewVars == <<block, vpc, status, shown, closeFailed>>
cacheVars == <<rows, fileExists>>
endVars == <<spc, snapshot, todo, keep, seen>>
waitVars == <<wpc, wresult, wOpen>>
vars == <<cmdVars, mirrorVars, viewVars, cacheVars, endVars, waitVars>>

Init ==
  /\ kind \in [Mirrors -> Kinds]
  /\ cmd = [m \in Mirrors |-> "running"]
  /\ cmdRc = [m \in Mirrors |-> NONE]
  /\ marker = [m \in Mirrors |-> NONE]
  /\ mpc = [m \in Mirrors |-> "start"]
  /\ killed = [m \in Mirrors |-> FALSE]
  /\ sigPending = [m \in Mirrors |-> FALSE]
  /\ blockKnown = [m \in Mirrors |-> FALSE]
  /\ listed = [m \in Mirrors |-> FALSE]
  /\ exitLine = [m \in Mirrors |-> NONE]
  /\ logExists = [m \in Mirrors |-> FALSE]
  /\ block = [m \in Mirrors |-> "none"]
  /\ vpc = [m \in Mirrors |-> "none"]
  /\ status = [m \in Mirrors |-> "none"]
  /\ shown = [m \in Mirrors |-> NONE]
  /\ closeFailed = [m \in Mirrors |-> FALSE]
  /\ rows = {}
  /\ fileExists = FALSE
  /\ spc = "idle"
  /\ snapshot = {}
  /\ todo = {}
  /\ keep = {}
  /\ seen = [m \in Mirrors |-> "unchecked"]
  /\ wpc = "idle"
  /\ wresult = "none"
  /\ wOpen = FALSE

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
  /\ UNCHANGED <<kind, mirrorVars, viewVars, cacheVars, endVars, waitVars>>

(* Claude Code stops the background task: SIGTERM to its process group.    *)
(* A running command dies before printf, so the pipe closes with no        *)
(* marker. The mirror's default action kills it at once, unless its        *)
(* rex_mirror.ts main() has run process.on("SIGTERM", ...): then the       *)
(* signal waits for the event loop. The viewer runs under the Rex server,  *)
(* outside the group.                                                      *)

HandlersOn(m) == mpc[m] = "reading" /\ Variant # "noSignalHandlers"

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
  /\ UNCHANGED <<kind, marker, blockKnown, listed, exitLine, logExists,
                 viewVars, cacheVars, endVars, waitVars>>

-----------------------------------------------------------------------------
(* rex_mirror.ts main()                                                    *)

\* writeFileSync(log, "", { flag: "wx" })
MirrorCreatesLog(m) ==
  /\ mpc[m] = "start"
  /\ mpc' = [mpc EXCEPT ![m] = "log"]
  /\ logExists' = [logExists EXCEPT ![m] = TRUE]
  /\ UNCHANGED <<cmdVars, killed, sigPending, blockKnown, listed, exitLine,
                 viewVars, cacheVars, endVars, waitVars>>

\* startViewer: inside spawnSync(`rex run ...`), the Rex server opens the block and starts the viewer.
MirrorOpensBlock(m) ==
  /\ mpc[m] = "log"
  /\ mpc' = [mpc EXCEPT ![m] = "asked"]
  /\ block' = [block EXCEPT ![m] = "open"]
  /\ vpc' = [vpc EXCEPT ![m] = "started"]
  /\ UNCHANGED <<cmdVars, killed, sigPending, blockKnown, listed, exitLine, logExists,
                 status, shown, closeFailed, cacheVars, endVars, waitVars>>

\* startViewer: `rex run` fails before it opens a block, and returns null.
MirrorGetsNoBlock(m) ==
  /\ mpc[m] = "log"
  /\ mpc' = [mpc EXCEPT ![m] = "replied"]
  /\ UNCHANGED <<cmdVars, killed, sigPending, blockKnown, listed, exitLine, logExists,
                 viewVars, cacheVars, endVars, waitVars>>

\* startViewer: spawnSync returns the JSON reply, and the mirror knows the block ID.
MirrorGetsBlockId(m) ==
  /\ mpc[m] = "asked"
  /\ mpc' = [mpc EXCEPT ![m] = "replied"]
  /\ blockKnown' = [blockKnown EXCEPT ![m] = TRUE]
  /\ UNCHANGED <<cmdVars, killed, sigPending, listed, exitLine, logExists,
                 viewVars, cacheVars, endVars, waitVars>>

\* startViewer: spawnSync hits its 15 s timeout after the block opened, and returns null.
MirrorTimesOut(m) ==
  /\ ReplyCanTimeOut
  /\ mpc[m] = "asked"
  /\ mpc' = [mpc EXCEPT ![m] = "replied"]
  /\ UNCHANGED <<cmdVars, killed, sigPending, blockKnown, listed, exitLine, logExists,
                 viewVars, cacheVars, endVars, waitVars>>

\* remember: one appendFileSync of one row, only when the block ID is known.
MirrorRemembers(m) ==
  /\ mpc[m] = "replied"
  /\ mpc' = [mpc EXCEPT ![m] = "remembered"]
  /\ IF blockKnown[m]
       THEN /\ rows' = rows \cup {m}
            /\ fileExists' = TRUE
            /\ listed' = [listed EXCEPT ![m] = TRUE]
       ELSE UNCHANGED <<rows, fileExists, listed>>
  /\ UNCHANGED <<cmdVars, killed, sigPending, blockKnown, exitLine, logExists,
                 viewVars, endVars, waitVars>>

\* openSync(log, "a") and the three process.on(...) calls.
MirrorInstallsHandlers(m) ==
  /\ mpc[m] = "remembered"
  /\ mpc' = [mpc EXCEPT ![m] = "reading"]
  /\ UNCHANGED <<cmdVars, killed, sigPending, blockKnown, listed, exitLine, logExists,
                 viewVars, cacheVars, endVars, waitVars>>

\* The `for await` loop sees end of input. The rest of main() and process.exit run with no
\* await between them, so no signal handler can run in between. A group kill posts the
\* signal to the mirror before any member exits and closes the pipe, so a pending signal
\* is handled first (SKILL.md, "Assumptions").
MirrorReadsEnd(m) ==
  /\ mpc[m] = "reading"
  /\ cmd[m] # "running"
  /\ ~sigPending[m]
  /\ mpc' = [mpc EXCEPT ![m] = "ended"]
  /\ exitLine' = [exitLine EXCEPT ![m] = IF marker[m] # NONE THEN marker[m] ELSE NOMARKER]
  /\ logExists' = [logExists EXCEPT ![m] = IF blockKnown[m] THEN @ ELSE FALSE]
  /\ UNCHANGED <<cmdVars, killed, sigPending, blockKnown, listed,
                 viewVars, cacheVars, endVars, waitVars>>

\* onSignal(143)
MirrorHandlesSignal(m) ==
  /\ mpc[m] = "reading"
  /\ sigPending[m]
  /\ mpc' = [mpc EXCEPT ![m] = "ended"]
  /\ exitLine' = [exitLine EXCEPT ![m] = SIGTERM]
  /\ logExists' = [logExists EXCEPT ![m] = IF blockKnown[m] THEN @ ELSE FALSE]
  /\ UNCHANGED <<cmdVars, killed, sigPending, blockKnown, listed,
                 viewVars, cacheVars, endVars, waitVars>>

-----------------------------------------------------------------------------
(* rex_mirror_view.ts main(), in the block. A close of the block ends it.  *)

Close(m) ==
  /\ block' = [block EXCEPT ![m] = "closed"]
  /\ vpc' = [vpc EXCEPT ![m] = IF @ = "closing" THEN "ended" ELSE @]

\* status("working", label)
ViewerReportsWorking(m) ==
  /\ vpc[m] = "started"
  /\ vpc' = [vpc EXCEPT ![m] = "working"]
  /\ status' = [status EXCEPT ![m] = "working"]
  /\ UNCHANGED <<cmdVars, mirrorVars, block, shown, closeFailed, cacheVars, endVars, waitVars>>

\* openSync(log, "r"): throws, and the viewer exits, when the log is gone.
ViewerOpensLog(m) ==
  /\ vpc[m] = "working"
  /\ vpc' = [vpc EXCEPT ![m] = IF logExists[m] THEN "reading" ELSE "crashed"]
  /\ UNCHANGED <<cmdVars, mirrorVars, block, status, shown, closeFailed,
                 cacheVars, endVars, waitVars>>

\* The read loop finds the exit line: status(done or error), closeSync, unlinkSync(log).
\* unlinkSync throws when the mirror already removed the log, and the viewer exits.
\* Variant "noViewerClose" is the viewer before 9338e63: it returns here.
\* Variant "closeBeforeStatus" is a broken viewer that closes the block first.
ViewerReadsExitLine(m) ==
  /\ vpc[m] = "reading"
  /\ exitLine[m] # NONE
  /\ IF Variant = "closeBeforeStatus"
       THEN /\ block' = [block EXCEPT ![m] = "closed"]
            /\ vpc' = [vpc EXCEPT ![m] = "ended"]
            /\ UNCHANGED <<status, shown, logExists>>
       ELSE /\ status' = [status EXCEPT ![m] = IF exitLine[m] = 0 THEN "done" ELSE "error"]
            /\ shown' = [shown EXCEPT ![m] = exitLine[m]]
            /\ logExists' = [logExists EXCEPT ![m] = FALSE]
            /\ vpc' = [vpc EXCEPT ![m] =
                         IF ~logExists[m] THEN "crashed"
                         ELSE IF Variant = "noViewerClose" THEN "ended"
                         ELSE "closing"]
            /\ UNCHANGED block
  /\ UNCHANGED <<cmdVars, mpc, killed, sigPending, blockKnown, listed, exitLine,
                 closeFailed, cacheVars, endVars, waitVars>>

\* After CLOSE_DELAY_MS, closeBlock: `rex block close` succeeds.
ViewerClosesBlock(m) ==
  /\ vpc[m] = "closing"
  /\ Close(m)
  /\ UNCHANGED <<cmdVars, mirrorVars, status, shown, closeFailed, cacheVars, endVars, waitVars>>

\* After CLOSE_DELAY_MS, closeBlock: `rex block close` fails or times out; main() returns.
ViewerCloseFails(m) ==
  /\ vpc[m] = "closing"
  /\ vpc' = [vpc EXCEPT ![m] = "ended"]
  /\ closeFailed' = [closeFailed EXCEPT ![m] = TRUE]
  /\ UNCHANGED <<cmdVars, mirrorVars, block, status, shown, cacheVars, endVars, waitVars>>

-----------------------------------------------------------------------------
(* session_end.ts main(), once.                                            *)

\* existsSync(path), then readFileSync(path).
EndReads ==
  /\ EndOn
  /\ spc = "idle"
  /\ IF fileExists
       THEN /\ spc' = "checking"
            /\ snapshot' = rows
            /\ todo' = rows
       ELSE /\ spc' = "finished"
            /\ UNCHANGED <<snapshot, todo>>
  /\ UNCHANGED <<keep, seen, cmdVars, mirrorVars, viewVars, cacheVars, waitVars>>

\* What newestState returns: "gone" for a closed block; for an open one, the newest
\* record's state ("null" when none), or "fail" for a rex timeout or non-JSON reply.
Answers(m) ==
  IF block[m] = "closed" THEN {"gone"}
  ELSE {IF status[m] = "none" THEN "null" ELSE status[m], "fail"}

Closes == IF Variant = "endPassKeepsError" THEN {"done"} ELSE Settled

\* One loop pass for one row: newestState, then `rex block close` or keep.push.
\* Variant "endPassKeepsError" is the hook before 9338e63. Variant "endPassAborts" is the
\* hook before d53f272: an unreadable reply throws, and the hook exits without a write.
EndChecks(m) ==
  /\ spc = "checking"
  /\ m \in todo
  /\ \E a \in Answers(m):
       /\ seen' = [seen EXCEPT ![m] = a]
       /\ todo' = todo \ {m}
       /\ IF a = "fail" /\ Variant = "endPassAborts"
            THEN /\ spc' = "aborted"
                 /\ UNCHANGED <<keep, block, vpc>>
            ELSE IF a \in Closes
            THEN /\ Close(m)
                 /\ UNCHANGED <<spc, keep>>
            ELSE /\ keep' = IF a = "gone" THEN keep ELSE keep \cup {m}
                 /\ UNCHANGED <<spc, block, vpc>>
  /\ UNCHANGED <<snapshot, cmdVars, mirrorVars, status, shown, closeFailed, cacheVars, waitVars>>

\* writeFileSync(path, keep) or unlinkSync(path). Rows appended since EndReads are lost.
EndWrites ==
  /\ spc = "checking"
  /\ todo = {}
  /\ spc' = "finished"
  /\ rows' = keep
  /\ fileExists' = (keep # {})
  /\ UNCHANGED <<snapshot, todo, keep, seen, cmdVars, mirrorVars, viewVars, waitVars>>

-----------------------------------------------------------------------------
(* wait-status.lua on the block of Watched, once. Events buffer from the   *)
(* start of the script, so the first read and the wait miss nothing.       *)

\* rex.block.call(program_status), then rex.block.call(process).
WaiterStarts ==
  /\ WaiterOn
  /\ wpc = "idle"
  /\ block[Watched] # "none"
  /\ wOpen' = (block[Watched] = "open")
  /\ IF block[Watched] = "closed"
       THEN /\ wpc' = "done"
            /\ wresult' = "not found"
       ELSE IF status[Watched] \in Settled
       THEN /\ wpc' = "done"
            /\ wresult' = status[Watched]
       ELSE IF vpc[Watched] = "crashed"
       THEN /\ wpc' = "done"
            /\ wresult' = "viewer exit"
       ELSE /\ wpc' = "waiting"
            /\ UNCHANGED wresult
  /\ UNCHANGED <<cmdVars, mirrorVars, viewVars, cacheVars, endVars>>

\* rex.wait returns on program_status_changed (settled) or on child_exited.
WaiterWakes ==
  /\ wpc = "waiting"
  /\ \/ /\ status[Watched] \in Settled
        /\ wresult' = status[Watched]
     \/ /\ status[Watched] \notin Settled
        /\ vpc[Watched] = "crashed" \/ block[Watched] = "closed"
        /\ wresult' = "viewer exit"
  /\ wpc' = "done"
  /\ UNCHANGED <<wOpen, cmdVars, mirrorVars, viewVars, cacheVars, endVars>>

-----------------------------------------------------------------------------

Next ==
  \/ \E m \in Mirrors, rc \in Codes : CommandEnds(m, rc)
  \/ \E m \in Mirrors :
       \/ Kill(m)
       \/ MirrorCreatesLog(m)
       \/ MirrorOpensBlock(m)
       \/ MirrorGetsNoBlock(m)
       \/ MirrorGetsBlockId(m)
       \/ MirrorTimesOut(m)
       \/ MirrorRemembers(m)
       \/ MirrorInstallsHandlers(m)
       \/ MirrorReadsEnd(m)
       \/ MirrorHandlesSignal(m)
       \/ ViewerReportsWorking(m)
       \/ ViewerOpensLog(m)
       \/ ViewerReadsExitLine(m)
       \/ ViewerClosesBlock(m)
       \/ ViewerCloseFails(m)
       \/ EndChecks(m)
  \/ EndReads
  \/ EndWrites
  \/ WaiterStarts
  \/ WaiterWakes

Spec == Init /\ [][Next]_vars

-----------------------------------------------------------------------------
(* The rules. SKILL.md gives each one a plain sentence and its harm.       *)

ExitLineWritten ==
  \A m \in Mirrors : mpc[m] \in {"ended", "dead"} /\ block[m] # "none" => exitLine[m] # NONE

ReportsCommandStatus ==
  \A m \in Mirrors : exitLine[m] # NONE =>
    \/ exitLine[m] = cmdRc[m]
    \/ killed[m] /\ exitLine[m] = SIGTERM

NoLostRow ==
  \A m \in Mirrors : listed[m] /\ block[m] = "open" => m \in rows

SettledBlockCloses ==
  \A m \in Mirrors :
    status[m] \in Settled /\ vpc[m] \in {"ended", "crashed"} /\ block[m] = "open" => closeFailed[m]

EndPassClosesSettledRows ==
  spc \in {"finished", "aborted"} =>
    \A m \in snapshot : seen[m] # "unchecked" /\ (seen[m] \in Settled => block[m] = "closed")

NeverCloseWorking ==
  \A m \in Mirrors : block[m] = "closed" => status[m] \in Settled

WaiterStartedOpenSeesOutcome ==
  wpc = "done" /\ wOpen => wresult \in Settled

LateWaiterSeesOutcome ==
  wpc = "done" => wresult \in Settled

=============================================================================
