# Spec template

Create specs under `docs/agents/specs/` unless the project or user specifies
another location; adjust the paths below accordingly. A spec records durable
approved intent; the selected tracker records executable task state.

## Frontmatter

- `status`: `draft`, `active`, `review`, `done`, or `archived`.
- `approved`: `false` until the complete proposal receives explicit approval.
- `desc`: one or two sentences for directory triage.
- `tracker`: `linear`, `github`, `local`, or another supported tracker.
- `tracker_container`: omit until a container exists; then record its stable id.
- `blocked` and `blocked_reason`: omit unless the spec itself is blocked.
- `created` and `updated`: ISO dates. Preserve `created`.

Optional authority or host-specific handoff details belong in prose when they
must survive a session. Do not use frontmatter as an action ledger.

<templates>

<template file="docs/agents/specs/NNNN-<slug>.md">
---
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
- **Authorized external actions**: <none, or the explicit authorized actions>
- **Stop for user input before**: <material scope decisions or actions lacking authority>
</template>

</templates>
