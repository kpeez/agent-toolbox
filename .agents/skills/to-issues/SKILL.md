---
name: to-issues
description: Break a plan, spec, or PRD into independently-grabbable issues on the project tracker using vertical tasks. Use when the user wants to convert a plan into issues, create implementation tickets, or break work down into issues.
---

# /to-issues

Break a plan into independently-grabbable issues using **vertical tasks**
(tracer bullets).

## Tracker

Pick the tracker at runtime — no per-repo config beyond an optional one-liner:

1. **Repo override** — if the repo's `AGENTS.md`/`CLAUDE.md`/`docs/agents/CONTEXT.md` names
   a tracker (e.g. `Issue tracker: linear (team ETHO, initiative Foo)` or
   `Issue tracker: github`), use it and pass along any extras on that line
   (team, initiative, labels, project). `CONTEXT.md` is the pin's home when
   `AGENTS.md` is a shared global file with no room for repo-specific lines.
2. **Prior specs** — else, if specs in `docs/agents/specs/` record a `tracker:`
   in their frontmatter and agree on one value, use it: what past runs actually
   used outranks any inference from where the code is hosted.
3. **Linear** — else, if Linear MCP tools are available:
   [references/issue-tracker-linear.md](references/issue-tracker-linear.md)
4. **GitHub** — else, if the repo has a GitHub remote and `gh` works:
   [references/issue-tracker-github.md](references/issue-tracker-github.md).
   **Public repos never reach this rung by fall-through**: agent process noise
   (tasks, progress comments) does not belong on a public issue list. If the
   repo is public (`gh repo view --json visibility`), use GitHub issues only
   when the repo override explicitly names `github`; otherwise continue to
   local markdown and tell the user which tracker to pin.
5. **Local markdown** — otherwise, files named `docs/agents/specs/NNNN-<slug>-issue-<NN>-<issue-slug>.md`:
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

Issues published by this skill are born triaged: label AFK tasks
`ready-for-agent` and HITL tasks `ready-for-human`. The labels are for the
benefit of issues arriving from *other* sources (humans filing bugs, external
reports) that must be triaged before work. **Tasks published from an approved
spec are ready by construction** — the implementation loop treats any unblocked
issue in the spec's container (project or parent issue) as workable and never
interrogates labels; only `ready-for-human` stops it.

## Process

### 1. Gather context

Work from what's already in context. If the user passes an issue reference
(number, URL, or path), fetch it and read its full body and comments.

### 2. Explore the codebase (optional)

If you haven't already, explore so issue titles/descriptions use the project's
own vocabulary (the `docs/agents/CONTEXT.md` glossary if present) and respect ADRs in
`docs/agents/adrs/` for the area you're touching.

Delegate the sweep rather than reading files yourself. On Claude, dispatch the
`swe:opencode-explorer` forwarder; if that Claude caller cannot nest, call
`mcp__plugin_swe_opencode-explorer__delegate` directly. On Codex, call that
plugin-delivered MCP tool directly with the absolute repository root as `cwd`
and `mode: "read-only"`. A missing or failed requested tool is reported to the
orchestrator; never silently substitute a host-native explorer or shell out to
`opencode run`.

### 3. Draft tasks as vertical cuts

Each issue is a thin task cutting through ALL layers end-to-end, never a
horizontal cut of one layer.

- Each task delivers a narrow but COMPLETE path through every layer (schema, API, UI, tests)
- A completed task is demoable or verifiable on its own
- Prefer many thin tasks over few thick ones

Mark each task **AFK** (an agent can implement and merge it with no human
interaction) or **HITL** (needs a human — architectural call, design review).
Prefer AFK where possible.

Then assign every task to a **changeset** — the tracker milestone collecting
the tasks that make up one reviewable change. The changeset, not the task, is
what the loop acts on: one implementer takes a whole changeset and it ships as
one pull request. `docs/agents/CONTEXT.md` holds the full hierarchy.

- A changeset is what one reviewer reads in one sitting, and what one
  implementer holds without losing the thread. Both fail at the same size.
- **A changeset too large for that is a spec that should have been split.**
  Say so and split the spec into part one and part two rather than filing the
  oversized changeset — nothing downstream will fix it, and a spec split is
  cheap now and expensive once implementation starts.
- A task that belongs with nothing else is a changeset of one. That is fine,
  and never a reason to invent a grouping.

### 4. Review the breakdown

Present the breakdown as a numbered list. Per task show: **Title**, **Type**
(AFK/HITL), **Blocked by** (which tasks must finish first). Check:

- Does the granularity feel right (too coarse / too fine)?
- Are the dependency relationships correct?
- Should any tasks be merged or split?
- Is each changeset one change a reviewer reads in one sitting? If any is
  not, the spec is too broad — split the spec, not the changeset.

**Who reviews depends on how you were invoked.** Splitting a spec that carries the
`approved: true` in its frontmatter (e.g. under `/start-loop`): the approval
already authorized publication — return the breakdown to the invoking
orchestrator for review and publish; do **not** prompt the user. Standalone use
on an unapproved plan: quiz the user and iterate until they approve.

### 5. Publish to tracker

If the work came from a spec (`docs/agents/specs/NNNN-<slug>.md`), publish it
into the tracker's **spec container**: on Linear, a **project** holding the
tasks as issues (see the Linear reference); on GitHub and local markdown, a
**parent issue** carrying the spec's goal/scope header, with the tasks as
child issues / sub-issues. Do NOT close or modify an existing container.

The container is resolved from the spec's own frontmatter
(`tracker`, `tracker_container`) per the tracker reference's "Container
identity" section — not by searching tracker bodies for a hidden token. If it
resolves, reuse that container and create only the missing tasks. If it names
a container that no longer exists, **stop**: creating a second one is the
failure this resolution order exists to prevent. Only when no container exists
do you create one, and then record its id on the spec so later runs resolve it
directly. Give the new container a plain `Spec: <specPath>` line for humans;
never write a machine-parsed token into its body.

The container is the remote-reviewable home for the "why," and from here the
tracker — not the local spec — is the task and status ledger.

Publish each approved task to the tracker in dependency order (blockers first)
so you can reference real issue identifiers in "Blocked by". Apply the triage
label (`ready-for-agent` / `ready-for-human`) at publish time.

Then set the spec's `status: active` — publication is the moment a draft becomes
real work. That property is the spec's own lifecycle, not a task ledger; the
tracker still owns every task and its state.

An **AFK** issue must be a durable **agent brief** — a future agent will pick it
up cold, with only the issue body for context. Write it so that's enough:

- **Behavioral, not procedural.** Describe the capability and its observable
  outcome, not a step-by-step recipe. Let the implementing agent choose the how.
- **No file paths or line numbers.** They go stale the moment someone refactors.
  Exception: a snippet from a scratch script (per `/tdd`) that encodes a
  decision more precisely than prose (state machine, reducer, schema, type
  shape) — inline just the decision-rich part and note where it came from.
- **Complete acceptance criteria.** An agent must be able to tell, unaided, when
  the work is done. Every criterion is checkable.
- **Explicit scope boundaries.** Say what's out of scope, so the agent doesn't
  wander into the next task or gold-plate this one.
- **Self-contained.** Resolve references ("the auth refactor") to the linked
  issue. Use the project's own vocabulary (`CONTEXT.md`) and respect `docs/agents/adrs/`.

A **HITL** issue can be terser — a human fills the gaps — but note _why_ it needs
a human (architectural call, design review, ambiguous trade-off).

Issue bodies are durable documentation: they need a clear
reader action, enough context to resume cold, and acceptance criteria that can be
checked without asking the original author.

Use this body:

```md
## What to build

Concise description of this vertical task — the end-to-end behavior, not
layer-by-layer implementation.

## Acceptance criteria

- [ ] Criterion 1 (observable, checkable)
- [ ] Criterion 2

## Scope

- In: <what this task covers>
- Out: <adjacent work that belongs to other tasks — do not touch>

## Blocked by

- <reference to blocking issue>, or "None — can start immediately"
```
