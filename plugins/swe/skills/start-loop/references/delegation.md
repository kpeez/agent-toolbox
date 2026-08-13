# Delegation — the dispatch contract

Context is the scarce resource. The lead's job is curating the smallest set of
high-signal tokens; subagents exist to keep exploration and implementation out
of the lead's context. Model recall degrades as a window fills, so every token
the lead holds must earn its place.

## Every dispatch prompt carries four things

1. **Objective** — the bounded task, specific enough that the worker never
   infers intent: name the files, the scenario, the acceptance behavior.
2. **Output contract** — the exact structured fields the lead will parse
   (`{status, branch, summary}` for implementers). Structure prevents the
   reason-one-way-act-another failure that free text invites.
3. **Tool and source guidance** — where to look first, which patterns to
   follow (by file path), what to leave alone.
4. **Boundaries** — what is out of scope, stated explicitly. Vague delegation
   measurably produces duplicated work and gaps.

The spec travels **verbatim, at the top** of the worker's prompt. Paraphrased
handoffs degrade like a telephone game, and mid-context instructions are
unreliably recalled. If the run needs something the spec lacks, fix the spec.

## Done is evidence, not self-report

Every worker gets a check it can run — tests, build, lint — so completion is a
pass/fail signal with output attached, never an assertion of success. The lead
re-runs the deterministic gates itself; the worker's green is a claim, the
gate's exit code is a fact.

## Artifacts down, summaries up

Workers write code and artifacts to disk and return a ~1–2k-token structured
summary plus paths. Never copy bulk output — diffs, logs, file contents —
through the lead's context; the lead holds reports, not work product.

## Fan-out rules

- Parallelize only genuinely independent slices: disjoint files, no shared
  state, no ordering. Interdependent tasks run in `after:` order.
- Writes stay single-threaded per slice; gate → merge → ship is strictly
  sequential.
- Scale effort to complexity: a simple task gets one worker with few tool
  calls; never spawn agents a task doesn't warrant. Multi-agent runs cost
  ~15× a chat session — spend it only where slices are truly parallel.
- Every worker has a hard turn/effort cap and a stall signal. A worker that
  exceeds its cap is a failed dispatch to redispatch or escalate, not
  something to wait on.

## Cost discipline

- Parallelism buys wall-clock time, not tokens. It never makes a run cheaper.
- Keep each role's prompt prefix byte-identical across dispatches — no
  timestamps, counters, or run state in the stable part — so prompt caching
  applies; warm the cache with one call before fanning out.
- Deterministic gates replace model re-checks: an exit code is cheaper and
  more reliable than a model re-examining itself.
- The final report accounts tokens by role; token spend is the primary
  performance and cost lever, so make it visible.

## Keep the harness dumb

Judge workers by end state (the diff, the gate results), not path adherence.
Do not bake model-behavior workarounds into dispatch logic — they go stale on
the next model and become dead weight; re-test any such workaround whenever a
role's model changes.
