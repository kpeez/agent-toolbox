---
name: write-spec
description: Create a feature spec — a local, pure-markdown design draft whose behaviors are verified by committed tests. Use when starting a new feature, when the task requires design thinking, touches multiple files, or spans sessions.
---

# /write-spec - Feature Spec Management

A spec is a **local, transient, pure-markdown design draft**. It exists to
force design thinking before code and to give the human a review gate. It is NOT a
status ledger: task and status truth live on the issue tracker (see `/to-issues`).
Once the design is settled and sliced into issues, the tracker is authoritative —
the local spec is authoring residue.

Specs are not user-written. A spec is the product of a `/sharpen` session (or an
approved plan-mode plan): the agent distills the sharpened plan into the `SPEC-<slug>.md`
goal/scope header and the user confirms it at the review gate. Durable decisions
surfaced by the sharpen go to committed `docs/adr/`, not the spec.

## The verification rule

This skill follows the `/implement` discipline. Read it before implementation:
describe behavior → prove it per `/tdd` (a failing test, or a red spike that
graduates into one) → implement until it passes.

## When to use a spec

Use a spec when any of these are true:

- The task requires design thinking or choosing between approaches
- The change touches multiple files or modules
- The work will span more than one session
- You're unfamiliar with the area of the codebase being modified
- The user explicitly asks for a plan or spec

Skip specs for trivial changes — typo fixes, single-line config changes, log line
additions, renames.

## If you're already in plan mode

Don't double-dip. Your approved plan **is** the sharpened input. Write it straight
to `specs/<slug>/SPEC-<slug>.md` as the goal/scope header, expand the design body below
the `---` divider, and flag the header for the user to confirm.

## Workflow

1. **Sharpen**: stress-test the plan with `/sharpen`; record durable decisions as ADRs
2. **Goal**: distill the sharpened plan into the `SPEC-<slug>.md` goal/scope header; the
   user confirms it
3. **Design**: expand the `SPEC-<slug>.md` design body after inspecting the repo
4. **Fork** — hand off or implement solo:
   - **Hand off (default when work will fan out):** run `/to-issues` to publish
     the spec as a parent issue + labeled sub-issues. Separate agents pick up
     each issue and run its own red → green → review → PR loop. The tracker owns
     status from here.
   - **Solo (single-slice spec, one sitting):** prove each behavior red-first
     per `/tdd` — a failing test, or a red spike that graduates into one —
     implement to green, then a host-native review pass, then `/pr`.

## /write-spec new <name>

Creates a feature spec directory with `SPEC-<slug>.md`.

<steps>
<step action="slugify">lowercase name, replace spaces with hyphens -> `<slug>`</step>
<step action="ensure-shared">ensure a repo-local `specs` symlink points at `$LLMOS_ROOT/projects/<repo>/specs` (skip if already linked); never create `specs` as a real committed directory in the source repo</step>
<step action="mkdir">`specs/<slug>/` (no-op if already present)</step>
<step action="create-root-agents">if `specs/AGENTS.md` is missing, create it from the template in `templates.md`</step>
<step action="create-files">read `templates.md` and write `SPEC-<slug>.md` to `specs/<slug>/`; never overwrite an existing `SPEC-<slug>.md` — a present goal/scope header is settled and authoritative</step>
<step action="populate">fill the goal/scope header from the sharpened plan (or approved plan-mode plan) and flag it for the user to confirm; if `SPEC-<slug>.md` already exists, leave its header alone. Then expand the design body below the `---` divider and name in the Verification section the behavior-level tests that will prove each behavior</step>
</steps>

## Spec structure

A spec is **`SPEC-<slug>.md`** — nothing more, and pure markdown: no code files
live under `specs/` (the shared specs directory may be an Obsidian vault).
Verification code lives in the repo — committed tests in the project's suite,
plus transient spike scaffolds (per `/tdd`) next to the module they exercise. Specs
must never be committed to the source repository. Keep `specs` ignored there
and point its repo-local symlink at the shared
`$LLMOS_ROOT/projects/<repo>/specs` directory.

```
specs/
├── AGENTS.md # How agents navigate specs; not a manual index
└── <feature>/
    └── SPEC-<slug>.md # Goal/scope header + agent-expanded design
```

`SPEC-<slug>.md` is one file, two zones split by a `---` divider: a short goal/scope
header (settled by the sharpen, confirmed by the user — preserve it, never
overwrite) and the agent-expanded design body. The sections and their meanings
are defined once, in `templates.md` — follow the template, don't improvise
structure.

Two semantics worth knowing beyond the template:

- **Execution mode**: `review-gated` (user reviews the design body before
  implementation — the default) or `autonomous` (the agent proceeds after writing
  the design, e.g. driven by `/goal`), plus stop conditions.
- **Durable decisions** (architecture, provider policy, storage model, security
  posture) go in committed `docs/adr/` (see `sharpen`'s `ADR-FORMAT.md`) and are
  linked from the Decisions section. The optional domain glossary is committed
  `CONTEXT.md` at the repo root.

## Documentation quality

Specs should
be plain Markdown that is easy to review in an editor, GitHub, or a tracker:
clear decision up front, explicit scope, nearby evidence, concrete validation,
and unresolved questions called out plainly.

## Status lives on the tracker

`/to-issues` selects the tracker (Linear MCP → GitHub → local markdown) and
publishes the header as a parent issue with labeled sub-issues. Status is the
issue state, blockers are the blocked-by links, the rollup is the parent view.
Before running out of context, drop a short progress comment on the active
issue — what's done, what's next, the one gotcha. That comment is the handoff.

## Verification lives in the test suite

Every spec behavior is proven by a runnable check that fails first: a test via
`/tdd`, or a spike that graduates into a behavior-level test (rules live in
`/tdd`'s spike section). These are executable
demonstrations at caller altitude — real imports, real call paths — not
unit-test theater. The spec's Verification section names them; the committed
tests ARE the durable record. Rerun them to verify current state, and paste the
run result into the issue comment for tracker-linked work.

## Resuming work on an existing spec

1. Read the tracker first — issue states, blocked-by links, latest progress comment
2. Read `SPEC-<slug>.md` for intent and design context
3. Run the tests named in the Verification section to see current state
4. Pick up the next unblocked `ready-for-agent` issue
5. Comment progress on the active issue before you hit a context limit
