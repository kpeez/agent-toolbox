---------------------------- MODULE PrLifecycle ----------------------------
EXTENDS Integers

CONSTANTS
  Prs,
  Requests,
  MaxPushes,
  StackMergeOn,
  Variant

PR == 1..Prs

VARIABLES
  request,
  pr,
  head,
  codeAt,
  vres,
  vpatch,
  trusted,
  readyBy,
  mergedAt,
  issue,
  issueMax,
  pushes

vars == <<request, pr, head, codeAt, vres, vpatch, trusted, readyBy, mergedAt,
          issue, issueMax, pushes>>
prVars == <<pr, readyBy, mergedAt>>
verdictVars == <<vres, vpatch, trusted>>
issueVars == <<issue, issueMax>>

Rank == [started |-> 0, review |-> 1, done |-> 2]

CanPublish == request \in {"publish", "finalize", "implement"}
CanLand == request = "implement"
Frontier(p) == \A q \in 1..(p - 1) : pr[q] = "merged"
PushKinds == IF Variant = "noiseCarry" THEN {"code", "noise"} ELSE {"code"}
Stands(p) ==
  /\ vres[p] = "pass"
  /\ \/ vpatch[p] = head[p]
     \/ Variant = "noiseCarry" /\ codeAt[p] <= vpatch[p]
MoveIssue(s) ==
  /\ issue' = s
  /\ issueMax' = IF Rank[s] > issueMax THEN Rank[s] ELSE issueMax

Init ==
  /\ request \in Requests
  /\ pr = [p \in PR |-> "none"]
  /\ head = [p \in PR |-> 0]
  /\ codeAt = [p \in PR |-> 0]
  /\ vres = [p \in PR |-> "none"]
  /\ vpatch = [p \in PR |-> -1]
  /\ trusted = [p \in PR |-> -1]
  /\ readyBy = [p \in PR |-> "none"]
  /\ mergedAt = [p \in PR |-> -1]
  /\ issue = "started"
  /\ issueMax = 0
  /\ pushes = 0

Publish ==
  /\ CanPublish \/ Variant = "proactivePublish"
  /\ \A p \in PR : pr[p] = "none"
  /\ pr' = [p \in PR |-> "draft"]
  /\ UNCHANGED <<request, head, codeAt, verdictVars, readyBy, mergedAt, issueVars, pushes>>

Push(p, kind) ==
  /\ pr[p] \in {"draft", "ready"}
  /\ pushes < MaxPushes
  /\ head' = [head EXCEPT ![p] = @ + 1]
  /\ codeAt' = IF kind = "code" THEN [codeAt EXCEPT ![p] = head[p] + 1] ELSE codeAt
  /\ pushes' = pushes + 1
  /\ UNCHANGED <<request, prVars, verdictVars, issueVars>>

GetVerdict(p) ==
  /\ CanLand
  /\ pr[p] \in {"draft", "ready"}
  /\ vpatch[p] # head[p]
  /\ \E r \in {"pass", "fail"} : vres' = [vres EXCEPT ![p] = r]
  /\ vpatch' = [vpatch EXCEPT ![p] = head[p]]
  /\ trusted' = [trusted EXCEPT ![p] = -1]
  /\ UNCHANGED <<request, prVars, head, codeAt, issueVars, pushes>>

Recheck(p) ==
  /\ CanLand
  /\ pr[p] \in {"draft", "ready"}
  /\ trusted' = [trusted EXCEPT ![p] = IF Stands(p) THEN head[p] ELSE -1]
  /\ trusted' # trusted
  /\ UNCHANGED <<request, prVars, head, codeAt, vres, vpatch, issueVars, pushes>>

MarkReady(p) ==
  /\ CanLand
  /\ pr[p] = "draft"
  /\ trusted[p] # -1
  /\ pr' = [pr EXCEPT ![p] = "ready"]
  /\ readyBy' = [readyBy EXCEPT ![p] = "land"]
  /\ UNCHANGED <<request, head, codeAt, verdictVars, mergedAt, issueVars, pushes>>

MergeGuard(p) ==
  /\ CanLand
  /\ pr[p] = "ready"
  /\ trusted[p] # -1
  /\ Frontier(p) \/ Variant = "anyVerifiedMerges"

Merge(p) ==
  /\ MergeGuard(p)
  /\ head[p] = trusted[p] \/ Variant = "unpinnedMerge"
  /\ pr' = [pr EXCEPT ![p] = "merged"]
  /\ mergedAt' = [mergedAt EXCEPT ![p] = head[p]]
  /\ UNCHANGED <<request, head, codeAt, verdictVars, readyBy, issueVars, pushes>>

MergeRefused(p) ==
  /\ MergeGuard(p)
  /\ head[p] # trusted[p]
  /\ Variant # "unpinnedMerge"
  /\ trusted' = [trusted EXCEPT ![p] = -1]
  /\ UNCHANGED <<request, prVars, head, codeAt, vres, vpatch, issueVars, pushes>>

StackMerge ==
  /\ CanLand
  /\ StackMergeOn
  /\ \A p \in PR : pr[p] = "ready" /\ trusted[p] # -1
  /\ pr' = [p \in PR |-> "merged"]
  /\ mergedAt' = head
  /\ UNCHANGED <<request, head, codeAt, verdictVars, readyBy, issueVars, pushes>>

FinalizeReady(p) ==
  /\ request = "finalize"
  /\ pr[p] = "draft"
  /\ pr' = [pr EXCEPT ![p] = "ready"]
  /\ readyBy' = [readyBy EXCEPT ![p] = "finalize"]
  /\ UNCHANGED <<request, head, codeAt, verdictVars, mergedAt, issueVars, pushes>>

ReadyOnRequest(p) ==
  /\ Variant = "readyOnRequest"
  /\ request \in {"publish", "implement"}
  /\ pr[p] = "draft"
  /\ pr' = [pr EXCEPT ![p] = "ready"]
  /\ readyBy' = [readyBy EXCEPT ![p] = "request"]
  /\ UNCHANGED <<request, head, codeAt, verdictVars, mergedAt, issueVars, pushes>>

IssueToReview ==
  /\ CanPublish
  /\ IF Variant = "reviewAfterMerge"
       THEN issue # "review" /\ \A p \in PR : pr[p] \in {"ready", "merged"}
       ELSE /\ Rank[issue] < Rank["review"]
            /\ \A p \in PR : pr[p] = "ready" /\ (readyBy[p] = "finalize" \/ trusted[p] # -1)
  /\ MoveIssue("review")
  /\ UNCHANGED <<request, prVars, head, codeAt, verdictVars, pushes>>

IssueToDone ==
  /\ issue # "done"
  /\ \A p \in PR : pr[p] = "merged"
  /\ MoveIssue("done")
  /\ UNCHANGED <<request, prVars, head, codeAt, verdictVars, pushes>>

TrackerClosesIssue ==
  /\ issue # "done"
  /\ pr[Prs] = "merged"
  /\ MoveIssue("done")
  /\ UNCHANGED <<request, prVars, head, codeAt, verdictVars, pushes>>

OldFinalizeMovesIssue ==
  /\ Variant = "finalizeMovesDone"
  /\ request = "finalize"
  /\ issue # "done"
  /\ \A p \in PR : pr[p] = "ready"
  /\ MoveIssue("done")
  /\ UNCHANGED <<request, prVars, head, codeAt, verdictVars, pushes>>

Next ==
  \/ Publish
  \/ \E p \in PR, k \in PushKinds : Push(p, k)
  \/ \E p \in PR : GetVerdict(p)
  \/ \E p \in PR : Recheck(p)
  \/ \E p \in PR : MarkReady(p)
  \/ \E p \in PR : Merge(p)
  \/ \E p \in PR : MergeRefused(p)
  \/ StackMerge
  \/ \E p \in PR : FinalizeReady(p)
  \/ \E p \in PR : ReadyOnRequest(p)
  \/ IssueToReview
  \/ IssueToDone
  \/ TrackerClosesIssue
  \/ OldFinalizeMovesIssue

MergedPatchVerified ==
  \A p \in PR : pr[p] = "merged" => vres[p] = "pass" /\ vpatch[p] = mergedAt[p]
DoneOnlyAfterMerge == issue = "done" => \A p \in PR : pr[p] = "merged"
IssueNeverBackward == Rank[issue] = issueMax
DraftUntilLandOrFinalize ==
  \A p \in PR : pr[p] \in {"ready", "merged"} => readyBy[p] \in {"land", "finalize"}
ActsWithAuthority ==
  /\ (\E p \in PR : pr[p] # "none") => CanPublish
  /\ (\E p \in PR : pr[p] = "merged") => CanLand
MergeAtFrontier == \A p \in PR : pr[p] = "merged" => Frontier(p)
=============================================================================
