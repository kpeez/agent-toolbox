---
name: write-spec
description: Create a feature spec — a local, pure-markdown design draft whose observable behaviors name independent oracles and acceptable evidence. Use when starting a new feature, when the task requires design thinking, touches multiple files, or spans sessions.
---

# /write-spec - Feature Spec Management

A spec is a **local, transient, pure-markdown design draft**. It exists to
force design thinking before code and to give the human a review gate. It is NOT a
status ledger: task and status truth live on the issue tracker (see `/to-issues`).
Once the design is settled and split into issues, the tracker is authoritative —
the local spec is authoring residue.

Specs are not user-written. A spec is the product of a `/sharpen` session (or an
approved plan-mode plan): the agent distills the sharpened plan into the `NNNN-<slug>.md`
goal/scope header and the user confirms it at the review gate. Durable decisions
surfaced by the sharpen go to the shared vault as ADRs under `docs/agents/adrs/`,
not the spec.

## The verification rule

Behavior is proven per `/implement` and `/testing-code` — read them before writing code.
The spec's Verification section names each observable claim, its independent
oracle, and acceptable evidence mode. Do not predeclare one committed test per
claim; exact test names are settled after exploration, and a claim may
legitimately cite a representative workflow, static check, reproducible demo, or
explicit no-permanent-test decision.

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
to `docs/agents/specs/NNNN-<slug>.md` as the goal/scope header, expand the design body below
the `---` divider, and flag the header for the user to confirm.

## Workflow

1. **Sharpen**: stress-test the plan with `/sharpen`; record durable decisions as ADRs
2. **Goal**: distill the sharpened plan into the `NNNN-<slug>.md` goal/scope header; the
   user confirms it
3. **Design**: expand the `NNNN-<slug>.md` design body after inspecting the repo
4. **Fork** — hand off or implement solo:
   - **Hand off (default when work will fan out):** run `/to-issues` to publish
     the spec into its tracker container (parent issue, or Linear project) with
     labeled task issues. Separate agents pick up
     each issue and prove behavior per `/testing-code` before review and PR. The
     tracker owns status from here.
   - **Solo (single-task spec, one sitting):** prove each behavior per
     `/testing-code`, then a host-native review pass, then `/ship-pr`.

## /write-spec new <name>

Creates a feature spec file `docs/agents/specs/NNNN-<slug>.md`.

<steps>
<step action="slugify">lowercase name, replace spaces with hyphens -> `<slug>`</step>
<step action="ensure-shared">run `/setup-repo` when the approved project-docs topology is missing; `docs/agents` must be a symlink pointing directly at `$LLMOS_ROOT/projects/<repo>`; never create `docs/agents` as a real committed directory in the source repo</step>
<step action="allocate-number">if an existing `docs/agents/specs/NNNN-<slug>.md` already matches this slug, reuse its number. Otherwise scan `docs/agents/specs/` for files matching `^[0-9]{4}-`, take the highest number, add 1, and zero-pad to 4 digits (start at `0001` if none exist) -> `<NNNN>`. Do this immediately before writing the file</step>
<step action="create-files">read `templates.md` and write `NNNN-<slug>.md` to `docs/agents/specs/`; never overwrite an existing spec file for this slug — a present goal/scope header is settled and authoritative</step>
<step action="populate">fill the goal/scope header from the sharpened plan (or approved plan-mode plan) and flag it for the user to confirm; if `NNNN-<slug>.md` already exists, leave its header alone. Then expand the design body below the `---` divider and map each observable claim in Verification to its independent oracle and acceptable evidence mode; settle exact committed test names only after exploration</step>
</steps>

## Spec structure

A spec is **`NNNN-<slug>.md`** — pure markdown with no code files
live under `docs/agents/specs/` (the shared specs directory may be an Obsidian vault). `/to-issues`
may create sibling local issue files named `NNNN-<slug>-issue-<NN>-<issue-slug>.md`.
Verification evidence lives with the work: permanent tests when they pass
`/testing-code`'s admission gate, other stable checks or reproducible demonstrations when
appropriate, plus transient scratch probes in gitignored `tests/temp/`. Specs
are never committed to the source repo; they live behind the gitignored
`docs/agents/` symlink (topology per the `ensure-shared` step above).

```
docs/agents/specs/
├── 0001-<slug>.md # Goal/scope header + agent-expanded design
└── 0002-<slug>.md
```

The numbering is the index — `ls` sorts it, the highest number is the newest.
Do not add a navigation or index file; it only drifts from the directory.

`NNNN-<slug>.md` is one file, two zones split by a `---` divider: a short goal/scope
header (settled by the sharpen, confirmed by the user — preserve it, never
overwrite) and the agent-expanded design body. The sections and their meanings
are defined once, in `templates.md` — follow the template, don't improvise
structure.

Two semantics worth knowing beyond the template:

- **Execution mode**: `review-gated` (user reviews the design body before
  implementation — the default) or `autonomous` (the agent proceeds after writing
  the design, e.g. driven by `/goal`), plus stop conditions.
- **Durable decisions** (architecture, provider policy, storage model, security
  posture) go in the shared vault as ADRs under `docs/agents/adrs/` (see
  `sharpen`'s `ADR-FORMAT.md`) and are linked from the Decisions section. The
  optional domain glossary is `docs/agents/CONTEXT.md`, in that same vault.

## Status lives on the tracker

See `/to-issues` for tracker ownership, status, blockers, and handoff rules.

## Verification evidence lives with the work

See `/testing-code` for choosing permanent tests, other acceptable evidence, and
disposable scratch probes.

## Resuming work on an existing spec

1. Read the tracker first — issue states, blocked-by links, latest progress comment
2. Read `NNNN-<slug>.md` for intent and design context
3. Run the verification evidence named in the Verification section to see
   current state
4. Pick up the next unblocked `ready-for-agent` issue
5. Comment progress on the active issue before you hit a context limit
