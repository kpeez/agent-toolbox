# agent-toolbox context

Issue tracker: linear

## The work hierarchy

One vocabulary, used everywhere — specs, skills, the conductor, tracker
artifacts, branch names. Nothing else names a unit of work.

| Term | What it is | Where it lives |
|---|---|---|
| **spec** | One design, small enough that its changesets each stay reviewable. Sprawl is split into part one and part two, never absorbed downstream. | `docs/agents/specs/NNNN-<slug>.md` |
| **changeset** | One reviewable change: the unit of work *and* of review. One implementer, one branch, one pull request. | a tracker milestone; branch `change/<ids>-<slug>` |
| **task** | One independently workable issue inside a changeset. A commit or a few. | a tracker issue |
| **stack** | The changesets of a run, bottom to top, each branch containing every branch below it, each PR based on the one below. | branch `stack/<n>`; bottom is the run's integration branch |
| **round** | Scheduling only: what the loop found workable at one moment. Never a branch, an artifact, or a review boundary. | the conductor's loop counter |

A changeset too large for one implementer is a spec that should have been split.
Do not cap, chunk, or otherwise absorb it downstream — fix the scope upstream,
where the fix is cheap and visible.
