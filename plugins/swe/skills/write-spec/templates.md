# Spec template

Create specs under `docs/agents/specs/` unless the project or user specifies
another location; adjust the paths below accordingly. A spec records durable
approved intent; the selected tracker records executable task state.

## Frontmatter

- `spec_id`: stable UUID4 for this spec; keep it unchanged across revisions.
- `status`: `draft`, `active`, `review`, `done`, or `archived`.
- `approved`: `false` until the complete proposal receives explicit approval.
  This flag is bookkeeping, not authority.
- `approved_revision`: the semantic revision digest of the approved content,
  recorded by the runtime; omit until approved.
- `desc`: one or two sentences for directory triage.
- `tracker`: `linear`, `github`, `local`, or another supported tracker.
- `tracker_container`: omit until a container exists; then record its stable id.
- `blocked` and `blocked_reason`: omit unless the spec itself is blocked.
- `created` and `updated`: ISO dates. Preserve `created`.

Operational handoff and resume state belongs in the private tracker issue packet
or current-state comment, not the spec. Use prose only for lasting decisions or
authority that must survive a session; do not use frontmatter as an action
ledger.

<templates>

<template file="docs/agents/specs/NNNN-<slug>.md">
---
spec_id: <uuid4>
status: draft
approved: false
desc: <one or two sentences on what this spec does>
tracker: <linear | github | local | supported tracker>
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---

# <Title>

## Goal

<!-- What outcome are we trying to achieve, and why? -->

## Scope

<!-- What is included? Name useful components or paths when they clarify scope. -->

## Non-goals

<!-- What adjacent work is excluded? -->

## Context index

<!-- Curated references the plan depends on. Include only what is relevant; do
     not index a whole vault. Separate the documentation root from the code
     repository, host, or artifact. Prefer a relative path or an approved link. -->
<!-- - id: <stable short id>
       title: <what it is>
       role: <spec | context | code | research | reference | policy>
       relevance: <the claim or decision it supports>
       documentation_root: <external configured documentation root identity>
       host: <host or service holding the documentation>
       path: <path relative to the declared documentation/code root>
                                      # or url: <approved usable link>
       revision: <commit or version>    # when known
       content_hash: <SHA256>           # required for local context
       knowledge_date: <YYYY-MM-DD>     # when the content was known current
       standing: <current | superseded | unknown>
       access: <local | remote | inaccessible | unchecked>
       disclosure: <public | internal | private>
       essential: <true | false> -->

## Success criteria

<!-- Observable outcomes that define success. -->

## Design

<!-- The proposed behavior and load-bearing implementation decisions. -->

## Decisions

<!-- Non-obvious feature choices and rationale. Link broadly durable decisions
     to docs/agents/adrs/ and assess whether existing ADRs still apply. -->

## Risks

<!-- Material failure modes, assumptions, and compatibility concerns. -->

## Verification

<!-- Map observable claims to independent oracles and proportionate evidence. -->
<!-- - Claim: <caller-visible behavior or high-risk invariant>
       Oracle: <how the expected result is known independently>
       Evidence: <test, workflow, static check, reproducible demonstration,
                  or explicit no-permanent-test decision> -->

## Execution and authority

- **Tracker container**: <link or identifier once created>
- **Approval source**: <durable source of the human decision; keep the computed
  digest in external approval bookkeeping, not inside the hashed Markdown>
- **Documentation roots / code roots**: <configured identities; relative paths below>
- **Meaningful legacy metadata**: <preserve; bookkeeping excluded from digest>
- **Authorized external actions**: <none, or the explicit authorized actions>
- **Stop for user input before**: <material scope decisions or actions lacking authority>
</template>

</templates>
