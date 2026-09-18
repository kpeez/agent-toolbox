# Workflow helpers

Existing task skills guide the workflow. This Python interface handles the
mechanical steps: validate and render a work packet, publish it safely, append
issue notes, and inspect current delivery evidence. It uses the standard library.

| File | Job |
|---|---|
| `workflow.py` | Installed interface v1 and preview/apply CLI |
| `core.py` | Packet checks, rendering, stable mappings, write intents and receipts |
| `adapters.py` | Linear GraphQL, read-only GitHub evidence, and an isolated fake |
| `audit.py` | One-shot read-only findings and suggested next steps |
| `demo.py` | Runnable synthetic publication and handoff example |
| `smoke.py` | A small set of offline regression checks |

Read the [Linear route](../../skills/to-issues/references/issue-tracker-linear.md)
for publication/privacy policy, and the [operation recipes](../../skills/to-issues/references/workflow-operations.md)
when a skill needs the CLI. Lab calls this same installed interface through its
launcher; configure `SWE_WORKFLOW_ENTRYPOINT` with an absolute installed path.

## Try it locally

Resolve the entry point from the installed SWE plugin, then run:

```sh
python3 /installed/swe/scripts/workflow/workflow.py capabilities
python3 /installed/swe/scripts/workflow/workflow.py demo --workdir /tmp/workflow-demo-new
python3 /installed/swe/scripts/workflow/smoke.py
```

The demo requires a new or empty directory. It creates synthetic files and a
fake tracker. Repeating publication reuses recorded identities. Normal commands
preview unless `--apply` is supplied; `audit` is always read-only.

## A controlled live pilot

Use external configuration for documentation roots/hosts, repositories and
integration branches, private Linear team/project/status/hold identifiers,
`LINEAR_API_TOKEN`, and optional `GITHUB_TOKEN` for required PR evidence. The
examples are inactive placeholders; no credentials or personal paths ship.
Verify the live schema with `capabilities --adapter linear --config ...`.
Set `live_pilot_enabled: true` only when live use is separately authorized.

Record revision-specific spec approval separately from publication or note
permission. Verify their actual human/session or operator-profile source before
applying; the [authority record](../../skills/to-issues/references/workflow-authorization.md)
is bookkeeping, not an authentication system. Todo and spec approval do not
authorize execution. Existing runner restrictions remain binding.

Use one supervised writer with one durable private state file. State holds
mapping/write receipts, not a second task tracker. A write intent saves its UUID
before the network call; retries inspect that identity before creating again.
Readback is required for a verified receipt. Later revisions use new documents
or comments so human text survives. Missing or archived mappings require
investigation. Do not copy an active state file to another worker or invoke
concurrent writers; this pilot provides no ownership arbitration.

Issue notes contain observed facts and next actions. The skills check holds,
ownership, dependencies, acceptance, and review; scripts do not execute tasks,
assign workers, launch jobs, change statuses, or mark Done. Handoffs belong in
Linear issues. Keep only reusable decisions or research conclusions in linked
documents. URL-only essential context needs a verified local copy for this CLI.

## Remaining milestones

1. Controlled live publication, readback, privacy/linkback and native skill checks.
2. If needed later, a persistent coordinator for distributed ownership, run
   observation and durable retry consumption; no worker or hooks ship here.
3. App-authored notifications, authenticated inbound replies, deliberate closure
   automation, and rollout. Each needs separate implementation and activation.

Offline checks and model reviews are local evidence. They do not prove live
notification delivery, background execution, scientific validity, or ownership.
