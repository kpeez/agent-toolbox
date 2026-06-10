---
name: to-issues
description: Break a plan, spec, or PRD into independently-grabbable issues on the project tracker using vertical slices. Use when the user wants to convert a plan into issues, create implementation tickets, or break work down into issues.
---

# /to-issues

Break a plan into independently-grabbable issues using **vertical slices**
(tracer bullets).

## Tracker

Pick the tracker at runtime — no per-repo config beyond an optional one-liner:

1. **Repo override** — if the repo's `AGENTS.md`/`CLAUDE.md` names a tracker
   (e.g. `Issue tracker: linear (team ETHO)` or `Issue tracker: github`), use it
   and pass along any extras on that line (team, labels, project).
2. **Linear** — else, if Linear MCP tools are available:
   [references/issue-tracker-linear.md](references/issue-tracker-linear.md)
3. **GitHub** — else, if the repo has a GitHub remote and `gh` works:
   [references/issue-tracker-github.md](references/issue-tracker-github.md)
4. **Local markdown** — otherwise, files under `specs/<feature>/issues/`:
   [references/issue-tracker-local.md](references/issue-tracker-local.md)

Read the matching reference before publishing; mention which tracker you used.
Other skills that say "the tracker" mean whatever this selection resolves to.

## Triage labels

Issues carry one of five canonical labels (in the local tracker, a `Status:` line):

| Label             | Meaning                                            |
| ----------------- | -------------------------------------------------- |
| `needs-triage`    | Needs evaluation before it can be worked           |
| `needs-info`      | Waiting on the reporter/user for more information  |
| `ready-for-agent` | Fully specified — an AFK agent can pick it up cold |
| `ready-for-human` | Requires human implementation or a human decision  |
| `wontfix`         | Will not be actioned                               |

Issues published by this skill are born triaged: label AFK slices
`ready-for-agent` and HITL slices `ready-for-human`.

## Process

### 1. Gather context

Work from what's already in context. If the user passes an issue reference
(number, URL, or path), fetch it and read its full body and comments.

### 2. Explore the codebase (optional)

If you haven't already, explore so issue titles/descriptions use the project's
own vocabulary (the `CONTEXT.md` glossary if present) and respect ADRs in
`docs/adr/` for the area you're touching.

### 3. Draft vertical slices

Each issue is a thin slice that cuts through ALL layers end-to-end, NOT a
horizontal slice of one layer.

- Each slice delivers a narrow but COMPLETE path through every layer (schema, API, UI, tests)
- A completed slice is demoable or verifiable on its own
- Prefer many thin slices over few thick ones

Mark each slice **AFK** (an agent can implement and merge it with no human
interaction) or **HITL** (needs a human — architectural call, design review).
Prefer AFK where possible.

### 4. Quiz the user

Present the breakdown as a numbered list. Per slice show: **Title**, **Type**
(AFK/HITL), **Blocked by** (which slices must finish first). Ask:

- Does the granularity feel right (too coarse / too fine)?
- Are the dependency relationships correct?
- Should any slices be merged or split?

Iterate until the user approves.

### 5. Publish

If the work came from a spec (`specs/<feature>/SPEC.md`), publish the spec's
goal/scope header as a **parent issue**, then publish the slices as **child issues
/ sub-issues** that reference it. This is the portable default — it works
identically on Linear and GitHub. Do NOT close or modify the parent issue.

Escalate to a **Linear project** only when the spec is large enough to span
milestones; then the slices are issues in the project rather than sub-issues. The
parent issue (or project) is the remote-reviewable home for the "why," and from
here the tracker — not the local spec — is the task and status ledger.

Publish each approved slice to the tracker in dependency order (blockers first)
so you can reference real issue identifiers in "Blocked by". Apply the triage
label (`ready-for-agent` / `ready-for-human`) at publish time.

An **AFK** issue must be a durable **agent brief** — a future agent will pick it
up cold, with only the issue body for context. Write it so that's enough:

- **Behavioral, not procedural.** Describe the capability and its observable
  outcome, not a step-by-step recipe. Let the implementing agent choose the how.
- **No file paths or line numbers.** They go stale the moment someone refactors.
  Exception: a blueprint-produced snippet that encodes a decision more precisely
  than prose (state machine, reducer, schema, type shape) — inline just the
  decision-rich part and note it came from a blueprint.
- **Complete acceptance criteria.** An agent must be able to tell, unaided, when
  the work is done. Every criterion is checkable.
- **Explicit scope boundaries.** Say what's out of scope, so the agent doesn't
  wander into the next slice or gold-plate this one.
- **Self-contained.** Resolve references ("the auth refactor") to the linked
  issue. Use the project's own vocabulary (`CONTEXT.md`) and respect `docs/adr/`.

A **HITL** issue can be terser — a human fills the gaps — but note *why* it needs
a human (architectural call, design review, ambiguous trade-off).

Use this body:

```md
## What to build

Concise description of this vertical slice — the end-to-end behavior, not
layer-by-layer implementation.

## Acceptance criteria

- [ ] Criterion 1 (observable, checkable)
- [ ] Criterion 2

## Scope

- In: <what this slice covers>
- Out: <adjacent work that belongs to other slices — do not touch>

## Blocked by

- <reference to blocking issue>, or "None — can start immediately"
```

Do NOT close or modify any parent issue.
