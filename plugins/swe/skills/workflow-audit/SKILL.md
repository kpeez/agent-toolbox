---
name: workflow-audit
description: Audit tracked workflow state against native tracker, mirror, context, and pull-request evidence and propose repairs. Read-only; not for broad workspace scans or unattended monitoring.
---

# /workflow-audit

Produce one scoped, read-only report of tracked workflow state and propose
evidence-backed repairs. This is a one-shot check of the workflow the caller
names, not a workspace scan and not a background service.

## Scope

Audit only the referenced workflow state: the approved spec and its packet,
native tracker state, content mirrors, curated context references, receipts, and
pull-request evidence. Read the specific resources the packet and receipts
identify. Do not walk the whole workspace on every invocation.

Separate confirmed matches from drift, missing mirrors, stale references, and
conflicting state, and list items that cannot be verified because evidence is
unavailable. Never report a clean result when verification did not pass.

## Propose, then apply only on request

The default output is findings plus proposed repairs, each tied to its evidence.
A default run does not mutate state.

Read [the operation interface](../to-issues/references/workflow-operations.md)
for scoped `audit` inputs and evidence requirements. Load the selected tracker
route only; for Linear, use [its authoritative reference](../to-issues/references/issue-tracker-linear.md).

Applying a repair requires both an explicit repair request and its own specific
existing authority. Audits never mutate state and there is no auto-Done.
Confirm the current options with:

```bash
python3 <installed SWE plugin>/scripts/workflow/workflow.py --help
```

Resolve that path relative to the installed SWE plugin resource, never from the
current working directory or a sibling plugin path. This skill's job is a
scoped read-only audit plus proposed repairs.

## Deferred

These are not delivered and must not be implied by this skill: distributed
claims, unattended reporting, notifications, webhook signatures or inbound
handling, and deployment or rollout. Do not add empty stubs for them.
