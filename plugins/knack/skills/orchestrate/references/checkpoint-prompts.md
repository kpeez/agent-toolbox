# Checkpoint prompts

One explicit question per transition. Only an unambiguous affirmative advances the
state machine. Silence, context compaction, or an unrelated reply is **not**
approval. A change request returns to the phase that produced the artifact under
review.

Each phase also opens with a restated **`/goal`** (a clear end state in your own
words) — and so does each worker you dispatch within it.

## 1. Sharpen → spec

> The design branches look resolved. Ready to turn this plan into the
> authoritative spec header? Reply `approve`, or name the decision still unsettled.

On approval, run `write-spec` and draft the goal/scope header.

## 2. Spec approval

> Approve `specs/<slug>/SPEC.md` (Goal, Scope, Non-goals, Success Criteria,
> Execution Mode, Validation) as ready for issue slicing? Reply `approve`, or list
> the changes.

On approval, add `<!-- knack:spec-approved -->` to the spec.

## 3. Publish issues (mutates external state — its own gate)

> Granularity, dependencies, and slice boundaries look right? Reply `approve` to
> publish to the tracker, or list changes.

On approval, create the parent (stamped with `<!-- knack-spec: <repo>/<slug> -->`)
and the vertical-slice children.

## 4. Begin implementation (mutates external state — its own gate)

> Published `<N>` slices under `<parent-id>`. Begin implementation now? Reply
> `approve`, `approve <child-id>`, or `stop`.

On approval, take the requested child or the next unblocked `ready-for-agent`
child, give the worker its own `/goal`, and run `implement`. Stop on a blocking
`ready-for-human` slice, a missing decision, failed verification, or a scope
change.
