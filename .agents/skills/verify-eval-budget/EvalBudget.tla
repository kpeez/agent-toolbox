---------------------------- MODULE EvalBudget ----------------------------
\* The eval-batch budget in evals/skills/run_eval.py: workers of one
\* `execute` process reserve, prepare, launch, and release runs, and a kill
\* followed by a rerun of the same --out (a resume) can come at any step.
\* Each action is one indivisible step of the code; SKILL.md maps them.
EXTENDS Naturals, FiniteSets

CONSTANTS
    Workers,      \* --jobs worker threads
    Runs,         \* plan items, each with its folder runs/<case>/<arm>/r<n>
    Stop,         \* runtime["per_run_stop_usd"]; plugin eval stops a run there
    Cost,         \* the known cost of an ended launch, below Stop
    Caps,         \* the --max-total-usd values explored
    Ends,         \* the run.json states a launch can end with
    MaxFailures,  \* MAX_CONSECUTIVE_FAILURES
    MaxRestarts,  \* kills and resumes explored
    InFlight,     \* "active": Batch.active set, spend skips it (now)
                  \* "counter": Batch.in_flight count (before 3df0eca)
    MoveAside     \* "reserve": Batch.reserve moves a stale folder (now)
                  \* "prepare": prepare moves it (before 9fb690e)

NoRun == "none"

VARIABLES
    record,      \* runs/<r>/run.json: "none", "started" (cost_usd null, no
                 \* ended_at), "known", "unknown" (ended, cost null),
                 \* "apiError" (ended with api_error and a known cost)
    asideKnown,  \* sum of known cost_usd in interrupted/*/run.json
    asideUnknown,\* count of interrupted/*/run.json with no known cost
    pc,          \* where each worker is in execute.one
    job,         \* the run each worker holds
    todo,        \* plan items this process has not handed to a worker yet
    active,      \* Batch.active
    inFlight,    \* Batch.in_flight
    stop,        \* Batch.stop, saved to stop.json: "none" or the reason
    failures,    \* Batch.failures
    cap,         \* --max-total-usd of this batch
    restarts,
    falseStop    \* a budget stop came while the next launch still fit

vars == <<record, asideKnown, asideUnknown, pc, job, todo, active, inFlight,
          stop, failures, cap, restarts, falseStop>>

Value(s) == CASE s \in {"known", "apiError"} -> Cost
              [] s \in {"started", "unknown"} -> Stop
              [] OTHER -> 0
Unknown(s) == s \in {"started", "unknown"}
Finished(s) == s \in {"known", "unknown"}
Bool2(b) == IF b THEN 1 ELSE 0

RECURSIVE SumOver(_, _)
SumOver(f, S) == IF S = {} THEN 0
                 ELSE LET x == CHOOSE x \in S : TRUE
                      IN f[x] + SumOver(f, S \ {x})

Holders == {w \in Workers : pc[w] # "idle"}
\* A holder's run.json is its own attempt once its launch has written it.
Owned == {job[w] : w \in {v \in Workers : pc[v] \in {"launched", "ended"}}}

\* The true worst case: known spend, plus Stop for each attempt with no known
\* cost, plus Stop for each reservation that has not been released.
TrueWorst ==
    asideKnown + Stop * asideUnknown
    + SumOver([r \in Runs |-> IF r \in Owned THEN 0 ELSE Value(record[r])], Runs)
    + Stop * Cardinality(Holders)

\* spend(out, Stop, skip)["worst_case_usd"] over a given record map.
Spend(rec, aK, aU, skip) ==
    aK + Stop * aU
    + SumOver([r \in Runs |-> IF r \in skip THEN 0 ELSE Value(rec[r])], Runs)

Init ==
    /\ record = [r \in Runs |-> "none"]
    /\ asideKnown = 0 /\ asideUnknown = 0
    /\ pc = [w \in Workers |-> "idle"]
    /\ job = [w \in Workers |-> NoRun]
    /\ todo = Runs
    /\ active = {} /\ inFlight = 0
    /\ stop = "none" /\ failures = 0 /\ restarts = 0
    /\ cap \in Caps
    /\ falseStop = FALSE

\* execute.one: `finished(run) or not batch.reserve(run)`. finished reads only
\* this run's folder, which no other worker touches, so it joins the step.
\* Batch.reserve holds Batch.lock for the move aside, spend, and the check.
Reserve(w, r) ==
    /\ pc[w] = "idle" /\ r \in todo
    /\ todo' = todo \ {r}
    /\ IF Finished(record[r]) \/ stop # "none"
       THEN UNCHANGED <<record, asideKnown, asideUnknown, pc, job, active,
                        inFlight, stop, falseStop>>
       ELSE
        LET moved == MoveAside = "reserve" /\ record[r] # "none"
            rec == IF moved THEN [record EXCEPT ![r] = "none"] ELSE record
            aK == IF moved THEN asideKnown + Cost * Bool2(record[r] = "apiError") ELSE asideKnown
            aU == IF moved THEN asideUnknown + Bool2(Unknown(record[r])) ELSE asideUnknown
            worst == IF InFlight = "active"
                     THEN Spend(rec, aK, aU, active) + (Cardinality(active) + 1) * Stop
                     ELSE Spend(rec, aK, aU, {}) + (inFlight + 1) * Stop
        IN /\ record' = rec /\ asideKnown' = aK /\ asideUnknown' = aU
           /\ IF worst > cap
              THEN /\ stop' = "budget"
                   /\ falseStop' = (falseStop \/ TrueWorst + Stop <= cap)
                   /\ UNCHANGED <<pc, job, active, inFlight>>
              ELSE /\ pc' = [pc EXCEPT ![w] = "reserved"]
                   /\ job' = [job EXCEPT ![w] = r]
                   /\ IF InFlight = "active"
                      THEN active' = active \cup {r} /\ UNCHANGED inFlight
                      ELSE inFlight' = inFlight + 1 /\ UNCHANGED active
                   /\ UNCHANGED <<stop, falseStop>>
    /\ UNCHANGED <<failures, cap, restarts>>


\* prepare(out, item, args), no lock. Before 9fb690e it moved the stale
\* folder aside here; se.materialize writes no run.json.
Prepare(w) ==
    /\ pc[w] = "reserved"
    /\ pc' = [pc EXCEPT ![w] = "prepared"]
    /\ LET r == job[w]
           moved == MoveAside = "prepare" /\ record[r] # "none"
       IN /\ record' = IF moved THEN [record EXCEPT ![r] = "none"] ELSE record
          /\ asideKnown' = IF moved THEN asideKnown + Cost * Bool2(record[r] = "apiError") ELSE asideKnown
          /\ asideUnknown' = IF moved THEN asideUnknown + Bool2(Unknown(record[r])) ELSE asideUnknown
    /\ UNCHANGED <<job, todo, active, inFlight, stop, failures, cap, restarts, falseStop>>

\* launch: the first save_json of run.json, with cost_usd null. No lock.
LaunchStart(w) ==
    /\ pc[w] = "prepared"
    /\ pc' = [pc EXCEPT ![w] = "launched"]
    /\ record' = [record EXCEPT ![job[w]] = "started"]
    /\ UNCHANGED <<asideKnown, asideUnknown, job, todo, active, inFlight, stop,
                   failures, cap, restarts, falseStop>>

\* launch: the last save_json of run.json. "started" stands for launch
\* raising after its first save, so run.json keeps a null cost. No lock.
LaunchEnd(w) ==
    /\ pc[w] = "launched"
    /\ pc' = [pc EXCEPT ![w] = "ended"]
    /\ \E s \in Ends :
          record' = [record EXCEPT ![job[w]] = s]
    /\ UNCHANGED <<asideKnown, asideUnknown, job, todo, active, inFlight, stop,
                   failures, cap, restarts, falseStop>>

\* Batch.release, under Batch.lock. halt keeps the first reason.
Release(w) ==
    /\ pc[w] = "ended"
    /\ LET s == record[job[w]]
           failed == s \in {"started", "unknown", "apiError"}
           f == IF failed THEN failures + 1 ELSE 0
       IN /\ failures' = f
          /\ stop' = IF stop # "none" THEN stop
                     ELSE IF Unknown(s) THEN "cost"
                     ELSE IF f >= MaxFailures THEN "errors"
                     ELSE "none"
    /\ pc' = [pc EXCEPT ![w] = "idle"]
    /\ job' = [job EXCEPT ![w] = NoRun]
    /\ IF InFlight = "active"
       THEN active' = active \ {job[w]} /\ UNCHANGED inFlight
       ELSE inFlight' = inFlight - 1 /\ UNCHANGED active
    /\ UNCHANGED <<record, asideKnown, asideUnknown, todo, cap, restarts, falseStop>>

\* The process dies at any step, and a rerun of the same --out starts a new
\* Batch: memory is lost, the folders and stop.json stay.
Resume ==
    /\ restarts < MaxRestarts
    /\ restarts' = restarts + 1
    /\ pc' = [w \in Workers |-> "idle"]
    /\ job' = [w \in Workers |-> NoRun]
    /\ todo' = Runs
    /\ active' = {} /\ inFlight' = 0 /\ failures' = 0
    /\ UNCHANGED <<record, asideKnown, asideUnknown, stop, cap, falseStop>>

Done ==
    /\ todo = {} /\ Holders = {} /\ restarts = MaxRestarts
    /\ UNCHANGED vars

Next ==
    \/ \E w \in Workers, r \in Runs : Reserve(w, r)
    \/ \E w \in Workers : Prepare(w) \/ LaunchStart(w) \/ LaunchEnd(w) \/ Release(w)
    \/ Resume
    \/ Done

Spec == Init /\ [][Next]_vars

\* Known spend plus Stop for each unknown or in-flight attempt stays in the cap.
CapSafe == TrueWorst <= cap

\* reserve refuses for budget only when the next launch would pass the cap.
NoFalseStop == ~falseStop
=============================================================================
