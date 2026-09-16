---
name: orchestrate
description: Coordinate bounded agents for substantial parallel work or independent review. Not for single-agent scoped edits or spec drafting.
---

# Orchestrate

Keep requirements, decisions, synthesis, and final acceptance with the lead.
Use the host's available delegation facilities and configured roles, choosing
the smallest capable agent. Delegation does not expand the user's scope or
authority and does not require a spec or tracker. This skill's job is bounded
coordination plus independent review.

## Assign bounded work

Give each worker the smallest complete brief: objective and acceptance
criteria, relevant requirements and source links, useful paths, file ownership,
constraints and authority, applicable checks, and a blocker route to the caller.
Include source text when the worker cannot access it. Request a concise result
with status, changed paths or artifacts, evidence, and unresolved concerns.

Delegate independent work in parallel only with isolated worktrees or disjoint
write ownership. Tell workers they are not alone and must preserve others'
changes. Do not make workers rediscover known context or return bulk logs when
stable paths and focused evidence suffice.

## Tracked coordination checklist

- Confirm the approved revision and explicit scope using the selected tracker
  route's approval mechanism. Todo status is distinct from permission.
- Respect holds, dependencies, and one owner per task; a worker reports to its
  caller and holds no cross-host claim.
- For configured Linear work, record `start`, `progress`, `handoff`, `review`, and `evidence` notes via
  `record` during the work (see
  [operations](../to-issues/references/workflow-operations.md)).
- Put handoff in the selected tracker issue (privately for Linear): state, verified evidence, next
  action, worktree and uncommitted work, jobs, and what not to repeat.
- Run independent review before human review; no PR, draft, or merge marks Done
  automatically.

## Integrate and follow up

Inspect worker results, resolve interactions, and verify the assembled outcome.
A worker report is an input, not final verification. For substantive changes,
use a reviewer who did not implement them; ask for concrete correctness,
requirement, verification, and unnecessary-complexity findings. Fix supported
findings and re-review when the changed risk warrants it.

Continue while evidence supports a useful in-scope next step. Diagnose repeated
failure before redispatching and stop loops that produce no new evidence.
Workers return consequential decisions and blockers to their caller. The lead
asks the user when progress requires a material scope or preference decision,
missing authority or capability, destructive action, or resolution of
contradictory requirements.
