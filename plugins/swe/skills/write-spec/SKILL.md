---
name: write-spec
description: Create a durable Markdown feature spec whose approved intent and observable behaviors guide tracked implementation work.
---

# /write-spec — feature spec management

Use `docs/agents/` for project documents unless the project or user specifies
another location. Create subdirectories as needed, whether tracked or ignored,
in an ordinary directory or through an existing symlink.

A spec records intended outcomes, scope, design, acceptance criteria, and
verification expectations. The selected tracker owns executable tasks,
dependencies, assignments, blockers, and progress. Do not duplicate that state
as a task checklist in the spec.

Specs are normally produced from `/sharpen` or an approved plan. Significant
decisions that apply beyond one feature belong in `docs/agents/adrs/` and link
back to the spec. The spec remains useful after tasks are created; it is not
authoring residue or an action journal.

## Approval and authority

The user approves the complete proposal before implementation. Set
`approved: true` only after explicit approval or when existing conversation
authority clearly covers the complete spec. An ADR, task size, or agent judgment
does not confer approval. Material changes to approved intent require renewed
approval; routine implementation choices do not.

Spec approval and tracker selection do not independently authorize external
tracker writes, commits, pushes, pull requests, deployment, or other external
mutations. Record applicable authority in the spec when it will matter across
sessions.

## Verification rule

The Verification section names each observable claim, its independent oracle,
and acceptable evidence. Do not require one committed test per claim. A stable
test, representative workflow, static check, reproducible demonstration, or an
explicit no-permanent-test decision may be proportionate evidence.

## When to use a spec

Use a spec when the work needs design choices, crosses files or modules, will
span sessions, enters unfamiliar code, or the user requests a plan or spec.
Skip it for a trivial, fully understood edit.

## Workflow

1. **Sharpen.** Resolve material ambiguity and record broadly durable decisions
   as ADRs.
2. **Draft.** Write the goal, scope, design, observable success criteria, and
   verification expectations after inspecting current project evidence.
3. **Approve.** Present the complete proposal unless existing explicit approval
   already covers it. Record that approval without asking for it again.
4. **Plan tasks.** Reuse linked tasks or invoke `/to-issues` for the approved
   scope. One task is sufficient when no split is useful. The selected tracker
   becomes the task and progress authority.
5. **Execute.** Read the spec for intent and the tracker for current work. A
   single bounded task may be implemented directly; a multi-task run may use
   `/execute-spec` when the user requests execution.

## /write-spec new <name>

Create `docs/agents/specs/NNNN-<slug>.md`:

1. Lowercase the name and replace spaces with hyphens.
2. Create the specs directory if needed.
3. Reuse the number of an existing matching slug. Otherwise scan files matching
   `^[0-9]{4}-`, allocate the next zero-padded number, and do so immediately
   before writing.
4. Read `templates.md`. Create the file without overwriting a settled spec.
5. Populate it from the sharpened or approved plan. Map observable claims to
   independent oracles and acceptable evidence. Exact retained tests can be
   chosen during implementation.

Specs are pure Markdown. Project conventions and canonical links live in
`docs/agents/CONTEXT.md`; executable tasks may be remote tracker items or local
sibling issue files. Do not add a generated navigation index.

## Resuming a spec

1. Read the spec for approved intent and the tracker for task state,
   dependencies, holds, assignments, and latest useful handoff.
2. Inspect the actual checkout, worktrees, diffs, commits, verification, and
   delivery state relevant to the next task.
3. Reconcile contradictions before acting. Tracker unavailability is a reported
   limitation, not evidence that no work remains.
4. Continue the next task whose ownership, dependencies, and authority can be
   established. Preserve unfinished and unrelated work.

See `/testing-code` and `/implement` for choosing and producing evidence.
