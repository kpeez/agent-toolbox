---------------------------- MODULE PluginRollout ----------------------------
EXTENDS Integers

CONSTANTS
    ClaudeDirs,  \* Claude Code config folders (CLAUDE_CONFIG_DIR values)
    ActiveDir,
    HermesDirs,
    PRs,
    Diffs,
    Variant

Catalogs == {"claude", "codex"}
Dirs == ClaudeDirs \cup HermesDirs
Edited == -1

AllDiffs == {"editCore", "editCoreBump", "addExtra", "addExtraClaudeOnly",
             "removeExtra", "removeExtraKeepEntry", "fileInExtra",
             "nameExtraSkill"}

ASSUME /\ ActiveDir \in ClaudeDirs
       /\ Diffs \subseteq AllDiffs
       /\ Variant \in {"today", "versionKey", "externalDirs", "noCatalogCheck",
                       "noIsolationCheck", "listedOnlyCheck"}
       /\ ("editCoreBump" \in Diffs => Variant = "versionKey")

VARIABLES
    tree,
    coreRev,
    head,       \* the number of commits on main; Claude Code's key is its SHA
    version,
    pr,
    diff,
    installed,
    key,
    checkout,
    ran

vars == <<tree, coreRev, head, version, pr, diff, installed, key, checkout, ran>>

FoldersListedIn(t) == t.extra => \A c \in Catalogs : t.entry[c]
EntriesPointIn(t) == (\E c \in Catalogs : t.entry[c]) => t.extra
NoNamesIn(t) == ~(t.names /\ t.extra)

Apply(t, d) ==
    CASE d = "addExtra" ->
            [t EXCEPT !.extra = TRUE, !.entry = [c \in Catalogs |-> TRUE]]
      [] d = "addExtraClaudeOnly" ->
            [t EXCEPT !.extra = TRUE, !.entry = [c \in Catalogs |-> c = "claude"]]
      [] d = "removeExtra" ->
            [t EXCEPT !.extra = FALSE, !.entry = [c \in Catalogs |-> FALSE]]
      [] d = "removeExtraKeepEntry" ->
            [t EXCEPT !.extra = FALSE, !.entry = [c \in Catalogs |-> c = "codex"]]
      [] d = "fileInExtra" -> [t EXCEPT !.extra = TRUE]
      [] d = "nameExtraSkill" -> [t EXCEPT !.names = TRUE]
      [] OTHER -> t

Clean(t, d) ==
    CASE d \in {"addExtra", "addExtraClaudeOnly"} -> ~t.extra
      [] d \in {"removeExtra", "removeExtraKeepEntry"} -> t.extra
      [] OTHER -> TRUE

(* The required repo-checks job: plugin_catalogs.py and plugin_isolation.py. *)
Gate(t) ==
    /\ Variant # "noCatalogCheck" => FoldersListedIn(t)
    /\ Variant \notin {"noCatalogCheck", "listedOnlyCheck"} => EntriesPointIn(t)
    /\ Variant # "noIsolationCheck" => NoNamesIn(t)

Init ==
    /\ tree \in {[extra |-> e, entry |-> [c \in Catalogs |-> e], names |-> FALSE] : e \in BOOLEAN}
    /\ coreRev = 0
    /\ head = 0
    /\ version = 0
    /\ pr = [p \in PRs |-> "none"]
    /\ diff = [p \in PRs |-> "editCore"]
    /\ installed = [d \in Dirs |-> 0]
    /\ key = [d \in ClaudeDirs |-> 0]
    /\ checkout = 0
    /\ ran = [d \in Dirs |-> TRUE]

PrOpens(p) ==
    /\ pr[p] = "none"
    /\ \E d \in Diffs : Clean(tree, d) /\ diff' = [diff EXCEPT ![p] = d]
    /\ pr' = [pr EXCEPT ![p] = "open"]
    /\ UNCHANGED <<tree, coreRev, head, version, installed, key, checkout, ran>>

(* GitHub runs the checks once, on the PR merged into main as main is now. *)
ChecksRun(p) ==
    /\ pr[p] = "open"
    /\ pr' = [pr EXCEPT ![p] =
                IF Clean(tree, diff[p]) /\ Gate(Apply(tree, diff[p])) THEN "green" ELSE "red"]
    /\ UNCHANGED <<tree, coreRev, head, version, diff, installed, key, checkout, ran>>

(* The ruleset requires green checks, but not a branch that is up to date. *)
PrMerges(p) ==
    /\ pr[p] = "green"
    /\ Clean(tree, diff[p])
    /\ tree' = Apply(tree, diff[p])
    /\ coreRev' = IF diff[p] \in {"editCore", "editCoreBump"} THEN coreRev + 1 ELSE coreRev
    /\ version' = IF diff[p] = "editCoreBump" THEN version + 1 ELSE version
    /\ head' = head + 1
    /\ pr' = [pr EXCEPT ![p] = "merged"]
    /\ ran' = [d \in Dirs |-> FALSE]
    /\ UNCHANGED <<diff, installed, key, checkout>>

(* README: `claude plugin marketplace update`, then `claude plugin update`.
   Both act on the config folder that CLAUDE_CONFIG_DIR names. *)
ClaudeUpdates(d) ==
    LET k == IF Variant = "versionKey" THEN version ELSE head
    IN /\ d \in ClaudeDirs
       /\ installed' = IF k # key[d] THEN [installed EXCEPT ![d] = coreRev] ELSE installed
       /\ key' = [key EXCEPT ![d] = k]
       /\ ran' = [ran EXCEPT ![d] = TRUE]
       /\ UNCHANGED <<tree, coreRev, head, version, pr, diff, checkout>>

(* README: `hermes -p <profile> plugins install ... --ref <sha> --force`, for each profile. *)
HermesInstalls(d) ==
    /\ d \in HermesDirs
    /\ Variant # "externalDirs"
    /\ installed' = [installed EXCEPT ![d] = coreRev]
    /\ ran' = [ran EXCEPT ![d] = TRUE]
    /\ UNCHANGED <<tree, coreRev, head, version, pr, diff, key, checkout>>

AgentEditsCheckout ==
    /\ checkout' = Edited
    /\ UNCHANGED <<tree, coreRev, head, version, pr, diff, installed, key, ran>>

CheckoutPulls ==
    /\ checkout' = coreRev
    /\ UNCHANGED <<tree, coreRev, head, version, pr, diff, installed, key, ran>>

Next ==
    \/ \E p \in PRs : PrOpens(p) \/ ChecksRun(p) \/ PrMerges(p)
    \/ \E d \in Dirs : ClaudeUpdates(d) \/ HermesInstalls(d)
    \/ AgentEditsCheckout
    \/ CheckoutPulls

(* Before 94537ee, a Hermes profile read the checkout through skills.external_dirs. *)
Loaded(d) ==
    IF d \in HermesDirs /\ Variant = "externalDirs" THEN checkout ELSE installed[d]

(* The update steps that the docs give. The Claude Code steps name no
   config folder, so they reach the active one. Each Hermes profile is named. *)
Documented(d) ==
    IF d \in ClaudeDirs THEN d = ActiveDir ELSE Variant # "externalDirs"

DocStepsRan == \A d \in Dirs : Documented(d) => ran[d]

DocStepsReachEveryFolder == DocStepsRan => \A d \in Dirs : Loaded(d) = coreRev
NeverLoadsUncommittedEdits == \A d \in Dirs : Loaded(d) # Edited
FoldersListed == FoldersListedIn(tree)
EntriesPointAtFolders == EntriesPointIn(tree)
NoCrossPluginNames == NoNamesIn(tree)

=============================================================================
