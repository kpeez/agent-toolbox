---
name: write-spec
description: Draft or revise a durable feature spec with scope, design decisions, and observable acceptance criteria. Not for tracker task creation, implementation, or publication.
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

## Approval, identity, and authority

Content approval, publication authorization, and execution permission are
distinct. A spec may be approved as content while publication and execution
remain separately authorized or withheld.

Keep the spec's identity stable with a UUID4 `spec_id`. For the configured Linear
workflow, bind approval to a semantic revision digest. Its runtime recomputes the digest from the spec
markdown and meaningful metadata, context references, and task requirements; it
excludes generated mappings, timestamps, `run_id`, status, and `approved`. A
material change to approved intent needs renewed approval. Bookkeeping, tracker
mappings, status, and run identifiers do not revoke content approval.

Set `approved: true` only after explicit approval, and treat it as
agent-editable bookkeeping rather than authority. Approval evidence is a
`spec_id`, semantic digest, approver, source, and date that the model checks
against the actual approval; other tracker routes retain their existing
explicit user-approval mechanisms. An ADR, task size, agent judgment, or generic
permission policy confers neither approval nor authority.

Spec approval and tracker selection do not independently authorize external
tracker writes, commits, pushes, pull requests, deployment, or other external
mutations. Record applicable authority in the spec when it will matter across
sessions, and preserve meaningful legacy fields and existing tracker mappings
unchanged rather than rewriting them.

## Verification rule

The Verification section names each observable claim, its independent oracle,
and acceptable evidence. Do not require one committed test per claim. A stable
test, representative workflow, static check, reproducible demonstration, or an
explicit no-permanent-test decision may be proportionate evidence.

## When to use a spec

Use a spec when the user requests a plan or spec, or when durable design
decisions and acceptance criteria are needed across sessions. Skip it for a
trivial, fully understood edit.

## Workflow

1. **Sharpen.** Resolve material ambiguity and record broadly durable decisions
   as ADRs.
2. **Draft.** Read [the spec template](templates.md) for the identity, metadata
   and context fields. Write the goal, scope, design, a curated context index, the
   observable success criteria, and verification expectations after inspecting
   current project evidence. Index only relevant references; never scan or index
   a whole vault. Check each entry against the template: documentation root or
   code repository, path/link, relevance, revision/knowledge date, standing and
   verified access. Preserve unknown values as explicit gaps; missing essential
   context metadata blocks approval instead of disappearing from the draft.
3. **Approve.** Present the complete proposal unless existing explicit approval
   already covers it. Record `spec_id` and the approved revision without asking
   for approval again.
4. **Deliver the requested planning artifact.** Finish with the spec, its
   approval state, and any unresolved decisions. Do not create tracker tasks or
   implement the spec in this workflow. If the user separately requests task
   creation or execution, use `/to-issues` or `/execute-spec` then.

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

## Revising an existing spec

1. Read the spec, current project context, and relevant decisions. Inspect only
   the files needed to keep scope, design, and acceptance criteria accurate.
2. Preserve settled approved intent unless the user authorizes a material
   change. Record unresolved contradictions instead of silently choosing one.
3. Return the revised spec and its approval state. Do not resume tracker tasks
   or implementation here; use `/execute-spec` for authorized execution.

See `/testing-code` and `/implement` for choosing and producing evidence.
