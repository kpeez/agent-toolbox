# Spec Templates

File templates for `/write-spec new`. Write each to its target path under `specs/`.

A spec is **`SPEC-<slug>.md` plus an `examples/` directory**: `SPEC-<slug>.md` (human goal +
agent design) and runnable verification scripts. Task and status truth live on the
issue tracker, not in a local file.

<templates>

<template file="specs/AGENTS.md">
# Specs

Specs are private working context and must never be committed. Keep `specs`
ignored in git; this directory may be a symlink to a private per-repo specs
directory.

Each spec lives in `specs/<slug>/` as `SPEC-<slug>.md` plus `examples/`.

Read order:

1. The tracker container/issue (entry point — status, blocked, latest progress)
2. `SPEC-<slug>.md` (goal + design)
3. `examples/` (runnable verification scripts)

Status and tasks live on the issue tracker (see `/to-issues`). Durable design
decisions do NOT live here — they go in committed `docs/adr/`. The optional
domain glossary lives in committed `CONTEXT.md` at the repo root.
</template>

<template file="specs/<slug>/SPEC-<slug>.md">
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

## Success Criteria

<!-- observable outcomes that define done -->

## Execution Mode

- **Mode**: review-gated
- **Stop and ask before**: destructive commands, production/shared infrastructure changes, credentials, broad rewrites, or scope changes

## Validation

<!-- commands/examples/tests that prove the goal -->

---

## Design

<!-- architecture, key components, patterns used (agent-expanded) -->

## Behavior

<!-- how does it work? inputs? outputs? this maps to example scripts -->

## Decisions

<!-- non-obvious choices: what we chose, why, alternatives considered.
     If a decision is durable beyond this feature (architecture, storage model,
     provider policy, framework choice), record it in docs/adr/ instead and
     link it here. -->

## Risks

<!-- what could break or needs careful verification -->

## Verification

<!-- maps example scripts to behaviors they verify -->
<!-- - `build_pipeline.py` -> proves the pipeline can be assembled -->
<!-- - `basic_pipeline_run.py` -> proves the happy-path execution works -->
</template>

</templates>
