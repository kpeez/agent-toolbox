# Spec Templates

File templates for `/write-spec new`. Write each to its target path under `docs/agents/specs/`.

A spec is **`NNNN-<slug>.md`** (human goal + agent design) — pure markdown, no
code files. Verification lives in the project's committed test suite. Task and
status truth live on the issue tracker, not in a local file.

## Frontmatter

Every spec opens with frontmatter. Keep it to these fields — they are the ones
this plugin's own commands read and write:

- `status` — `draft` on creation. `/to-issues` advances it to `active`,
  `/ship-pr` to `review`, and `/ship-pr finalize` closes it at `done`. Use
  `archived` for abandoned or superseded specs. This is the spec's lifecycle,
  not its task list.
- `desc` — one or two sentences on what the spec does. Written at creation so a
  reader can triage a directory of specs without opening them.
- `blocked` / `blocked_reason` — omit unless actually blocked. Blocking is
  orthogonal to `status`: a spec is blocked *at* a phase, so record both.
- `created` / `updated` — ISO dates. Preserve `created`; bump `updated` on
  meaningful edits.

Do not add fields for a note system here. A vault that indexes these specs owns
its own properties and stamps them itself.

<templates>

<template file="docs/agents/specs/NNNN-<slug>.md">
---
status: draft
desc: <one or two sentences on what this spec does>
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---

# <Title>

<!--
Two zones in one file:
- Goal/Scope/Non-goals/Success/Validation = the settled plan from the sharpen
  session, confirmed by the user. Preserve it; never overwrite an existing header.
- Design and below = agent-expanded after inspecting the repo.
-->

## Goal

<!-- what problem are we solving and why -->

## Scope

<!-- what is included -->

## Non-goals

<!-- what is explicitly out of scope -->

## Success criteria

<!-- observable outcomes that define done -->

## Execution mode

- **Mode**: review-gated
- **Stop and ask before**: destructive commands, production/shared infrastructure changes, credentials, broad rewrites, or scope changes

## Validation

<!-- commands/tests that prove the goal -->

---

## Design

<!-- architecture, key components, patterns used (agent-expanded) -->

## Behavior

<!-- how does it work? inputs? outputs? each behavior maps to a test -->

## Decisions

<!-- non-obvious choices: what we chose, why, alternatives considered.
     If a decision is durable beyond this feature (architecture, storage model,
     provider policy, framework choice), record it in docs/agents/adrs/ instead and
     link it here. -->

## Risks

<!-- what could break or needs careful verification -->

## Verification

<!-- maps committed tests to the behaviors they pin -->
<!-- - `tests/test_pipeline.py::test_pipeline_assembles_from_config` -->
<!-- - `tests/test_pipeline.py::test_happy_path_run_produces_output` -->
</template>

</templates>
