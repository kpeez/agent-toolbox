# Program rules

Read this reference from the [run-program](../playbooks/run-program.md)
playbook. It holds the roles, the store, the brief, the drain, stack safety,
verification, failure handling, and escalation for a standing program.

Ceremony must scale with the program. On cheap near-identical units, collapse
it as each section directs. Three rules carry the rest:

- Completions are queue events, not interrupts.
- Every spawn and every resume carries the standing orders verbatim.
- The brief is the product. A vague brief fails quietly, because a worker
  cannot ask you a question.

## Roles and placement

- **Coordinator (this session).** Frames, authors briefs, drains the inbox,
  owns the human report, and makes judgment calls. It never authors or edits
  code. Conflicted merges, chain rebases, and code changes are always tasks.
  Mechanically landing a verified unit (a fast-forward or clean cherry-pick of
  a worker's commit, then a push) is bookkeeping the coordinator may do itself
  where local git is cheap. Work queued behind an idle stacker is how a
  deadline harvests nothing. Spawn, resume, and drain agents only through the
  host's subagent tool. In Claude Code, code workers are `swe:daedalus`; pick
  `opus` for judgment and the hardest code, `sonnet` for routine code, and
  `haiku` for mechanical edits. In Codex, pick the reasoning effort. Read and
  write store files only at drain points.
- **Sub-coordinator.** Durable, one per track, and only when the program
  exceeds what one coordinator's drains can handle. A track the coordinator
  can drain itself needs no middle layer, because each nested layer pays a
  full orientation again, and a blocking sub-coordinator hides its children
  while the parent idles. It owns its track's units and rows, authors its
  workers' briefs, spawns its own workers and verifiers, and rolls up at wave
  boundaries. It never forwards raw child reports. Cap in-flight children at
  what one drain can process, about ten, as a rolling window, never as
  blocking batches.
- **Worker or verifier.** Prefer a cloud session or an isolated worktree.
  Keep a worker local only when the task needs this machine: runtime
  verification through the project's verification skill, local session
  transcripts, simulators, or auth that exists only here. A cloud worker
  cannot read the local store, so its brief inlines what it needs or points
  at repository paths. Prefer fewer, broader workers. Give each worktree or
  branch one writer
  ([separate-before-serializing-shared-state](../../principle-separate-before-serializing-shared-state/SKILL.md)).
  Run a unit's verifier on a different model from its worker: another Claude
  model, or an external provider through the `orchestrate` skill when the
  user has one.

Depth stays at coordinator, track, and worker. Author the track decomposition
per project. Build, landing, and verification are common cuts, not a required
shape.

## Store

Keep the store as plain files in `<plans dir>/program-<slug>/`. Find the
plans directory with `python3 <plugin-root>/scripts/handoff.py dir`. Every
file has exactly one writer. Owners publish facts, and readers aggregate at
read time. Write each table with a header row and one row per line, tab
separated. Rewrite a changed table whole, through a temporary file and a
rename, so a crash never leaves half a row.

- `preferences.md` is the standing-orders register. It holds numbered lines,
  one constraint each: model policy, stack shape and count, verification bar,
  forbidden paths, escalation policy, and the stacker for each stack. Paste
  it verbatim into every spawn and every resume. Directives decay across
  resumes, and each dropped one costs a human turn. When you catch yourself
  restating an instruction, append the line before you act
  ([encode-lessons-in-structure](../../principle-encode-lessons-in-structure/SKILL.md)).
- `overview.md` is the durable PR and issue record. Append to it. Do not
  rewrite it for each event.
- `units.tsv` has the columns `id track state branch pr sha brief`. Update a
  row in place.
- `frontier.json` is the computed merge frontier. See
  [Stack safety](#stack-safety).
- `ledger.tsv` has the columns `pr sha verdict evidence verifier ts`. See
  [Verification](#verification).
- `inbox.tsv` has the columns `ts agent unit status report`, one row per
  completion. A drain moves its rows to `inbox-drained.tsv`.
- `gates.md` parks human gates. Each gate has an id, the question, the
  options, and the default on no answer.
- The decision log is the trail, per the `log-decisions` skill.
- `status.md` is derived from `units.tsv` and `ledger.tsv` at each drain. Do
  not maintain it by hand. Regenerate it from the tables. Do not narrate
  events into it.

## The brief

Your prompts to agents are your only product. A sloppy brief compounds into
slop across the whole tree. Every spawn carries every field of the
`orchestrate` skill's brief (goal, scope, context, acceptance, verify,
timebox, forbidden, report), plus these:

- **Forbidden** always holds: no PR retargets or merges, no rebase, no
  force-push, no fixes outside scope, plus unit-specific bans.
- **Report** always asks for status, branch, head SHA, PRs, verdict, what the
  worker actually ran, deviations, and suggested follow-ups.
- **Standing** holds `preferences.md` pasted verbatim.

A field you cannot fill is a unit you have not scoped yet. Size the brief to
the unit. A one-command unit gets one paragraph that names the goal, scope,
verify command, and report shape. Local spawns may reference the standing
orders by store path. Paste them verbatim for cloud spawns and every resume.

A sub-coordinator brief adds its track boundary and unit list, its spawn
budget with the cloud default and the local exceptions, the drain protocol,
and the rollup format. The rollup gives, per child, the name, status, PR,
head SHA, verdict, and one line, plus the track status and frontier change.

A dependency is a context relay, not only an ordering. Paste the upstream
report into the downstream brief, or the worker guesses. A missing field is a
refuse-to-spawn condition. Audit one sampled worker brief per sub-coordinator
per wave, alongside the wave it samples, never as a gate in front of it. A
failing brief stops that track and fixes the sub-coordinator's instructions,
not just the worker's brief, because brief quality decays late in a run.
Never resume-chain a brief. Respawn fresh with consolidated scope.

## Queue and drain

- On a completion notice, append one row to `inbox.tsv` and return to what
  you were doing. Do not review inline. A completion that needs review
  becomes a verifier unit. Never review a diff inside a drain.
- Drain in batches at four points: the end of a critical section, a track
  rollup, a frontier watcher wake, and before a human report. Arm the watcher
  with Claude Code's `/loop`, with a long heartbeat as the fallback. Arrivals
  during a drain wait for the next drain.
- Finish a critical section before a drain: authoring a brief, a stack
  operation, a conflict decision, writing a gate, or updating the ledger or
  frontier.
- Each drain classifies every row (landed, needs-verify, failed, zombie,
  noise), updates `units.tsv` and `ledger.tsv`, regenerates `status.md`, then
  spawns the next wave in one message.
- Account for every spawned child at its track's rollup: arrived, respawned,
  or its scope explicitly absorbed. Silently redoing a missing child's work
  hides both the wasted spend and the coverage gap.
- A drain turn ends with three lines: counts against the states, what
  changed, and open gates. Detail lives in `status.md`. The full reply applies
  at checkpoints and at close.

## Stack safety

- The frontier is a computed object, never narrative. Recompute
  `frontier.json` after every merge and stack change. It holds the ordered PR
  list (bottom to top), branch names, head SHAs, a generation number that
  rises by one per recompute, and the lowest unmerged PR. Read the PR states
  and bases with
  `gh pr list --state all --json number,headRefName,baseRefName,state,headRefOid`,
  walk the base chain from trunk to the stack tip, and take each head SHA
  from the stacker's clone. A branch with no PR is an error, not a guess.
- Exactly one stacker per stack may change topology (chain rebases,
  force-pushes, base retargets, merges), one operation at a time. Record the
  stacker in the standing orders. Run chain rebases in a cloud session or a
  dedicated worktree.
- Workers never rebase, retarget, or merge PRs. Babysitters follow the
  [babysit-pr](../playbooks/babysit-pr.md) playbook, one per stack, scoped to
  one frontier generation. They report conflicts to the stacker and do not
  rebase.
- PR closes and retargets go through the stacker only. Closing a base PR
  orphans every chain above it. Merges and stack surgery are units with
  briefs like any other.
- One retro watcher follows merged PRs for reverts, post-merge CI breaks, and
  orphaned follow-ups.

## Verification

Scale verification to the unit. When the verify field is one cheap command,
the worker runs it and reports the output, and the coordinator spot-checks
the receipts. A dedicated verifier agent, on a different model from the
worker, is for units whose verification is expensive, judgment-heavy, or
high in blast radius. A verifier whose whole product is a rerun of one
command is ceremony, not verification.

`ledger.tsv` has one row per verdict, keyed by PR number plus head SHA. The
verdict is one of `live-ui-verified`, `unit-test-verified`,
`type-check-only`, `verifier-blocked`, or `verifier-failed`. CI green is an
input to a verdict, not a verdict. Behavioral work needs better than
`type-check-only`. `verifier-blocked` is not a pass; respawn when the
environment heals. `verifier-failed` gets a fix unit, not a re-verify. A
worker may self-report, and a verifier overrides it on the same key. A new
head SHA voids the row, so re-verify after a restack. The ledger answers
"was this verified", not memory and not the transcript.

A unit is not done until its output leaves the worker the moment it lands.
The worker pushes its branch, the verifier writes its ledger row, and the
receipts land in the store. Work that exists only in one session when that
session dies was never done.

## Liveness and failure

- Never resume an agent to check on it, because a resume restarts an idle
  agent. Probe read-only: the ledger, `units.tsv`, `gh`, pushed branches, and
  the cloud session's status. A transcript's modified time is not liveness.
- A silent death gets a synthetic postmortem row in the inbox: unit, failure
  mode, last evidence, and options. Replan on evidence as it arrives. Never
  wait for full quiet.
- Retry by mode. A cap hit or out-of-memory respawns with smaller scope. A
  network drop retries as is. A tool error retries on a different model. An
  unknown failure retries once. After two retries, abandon the unit and
  replan around it.
- A zombie that returns hours late reconciles against the current frontier
  and ledger before anything is accepted. Salvage unique findings through a
  fresh unit, never a blind merge.
- When continued spawning would produce garbage across the tree (bad
  upstream output, broken acceptance, dead infrastructure), write a stop line
  at the top of the standing orders, let in-flight work finish, fix the
  cause, and clear the line.
- Bound your own infrastructure retries as you bound a child's. After a few
  consecutive tool failures, stop. Write a terminal handoff with the
  `handoff` skill (what is done, where it lives, and the exact command to
  resume) and end the run.
- After a host restart, local agents are dead and cloud work is not. Re-read
  the standing orders and `units.tsv`, recompute the frontier, reattach cloud
  work by PR and branch rather than agent id, respawn one sub-coordinator per
  track from its stored brief plus the current state, drain, and resume.

## Escalation

These reach the human, batched into the status report rather than sent one
by one: irreversible actions (force-push to shared branches, deploys,
deletions, closing someone else's PR), genuine product or preference calls
that no experiment settles, a standing order that contradicts observed
reality, and a program-level dead end that survived a replan. Park each as a
`gates.md` entry before you ask, and route work around it.

These never reach the human: frontier nudges, rebase mechanics, retries, CI
flake triage, review-thread triage, format fixes, scope the brief already
forbids (refuse and continue), and "should I keep going". When in doubt, act
and log.

Mid-run discoveries fix only what blocks the frontier. Everything else parks
in follow-ups. At this fan-out, a small scope leak multiplies into PRs nobody
asked for.
