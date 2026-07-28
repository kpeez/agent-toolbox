# Checkpoint prompts

Two gates, both during design, both on `/start-loop`'s **gated path** — the
route triage takes when any policy criterion fails. One explicit question per
transition; only an unambiguous affirmative advances the state machine. Silence,
context compaction, or an unrelated reply is **not** approval. A change request
returns to the phase that produced the artifact under review.

On the **autonomous path** (all triage criteria pass) neither prompt is asked:
the lead stamps the approval marker itself and records a gate-record comment on
the tracker container in their place. The record, not a prompt, is the oversight
artifact.

Each phase also opens with a restated **`/goal`** (a clear end state in your own
words) — and so does each task worker you dispatch within it.

## 1. Sharpen → spec

> The design branches look resolved. Ready to turn this plan into the
> authoritative spec header? Reply `approve`, or name the decision still unsettled.

On approval, run `write-spec` and draft the goal/scope header.

## 2. Spec approval — the last prompt

> Approve `docs/agents/specs/NNNN-<slug>.md` (Goal, Scope, Non-goals, Success Criteria,
> Execution Mode, Validation)? On `approve` I'll slice it into issues, publish
> them, and run the implementation loop to completion — no further prompts.
> Reply `approve`, or list the changes.

On approval, add `<!-- knack:spec-approved -->` to the spec. That marker is the
standing authorization for everything downstream — it is what the graph
conductor requires before it will run.

## After approval: launch, then escalate

There are no publish or implement gates. Launch the `knack-graph` workflow with
the handoff tuple per `start-loop`'s "Launch the graph" section; slicing,
implementation, review, and shipping are the conductor's, not a phase you run in
prose. Escalations come back in the run summary — what to resolve yourself
versus when to interrupt the user is in `start-loop`'s "Escalation, not gates"
section. Follow it.
