# Project context

`.agents/docs/CONTEXT.md` holds the small amount of reusable project knowledge
that a new session needs: purpose, terminology, non-obvious constraints, useful
quirks, and links to canonical documents. Follow an explicit project or user
override of this default location. Create it only when useful context exists,
whether tracked or ignored, in a directory or through an existing symlink.

Keep each fact in one home:

- `AGENTS.md`: verified repository commands and recurring work conventions.
- `CONTEXT.md`: project context and glossary; the tracker pin may live here when
  `AGENTS.md` is shared across repositories.
- Plan (`<main checkout>/.agents/plans/`, untracked): a short-lived handoff for large work;
  the merged pull request replaces it as the record.
- Tracker: issues, dependencies, progress and current blockers.
- ADR: a historical choice, its assumptions, and the rationale for comparing
  alternatives. It is not a current requirement or permission grant.

For a binding constraint, link to its current source (such as an explicit user
requirement or contract), not just the ADR that once mentioned it. Uncertain
applicability is a question to resolve, not permission to ignore the constraint.

Link to those records instead of copying them. Personal preferences and agent
memory belong with the agent, not in project context. Do not keep an action
ledger, session transcript, or duplicate task status here.

## Optional shape

```md
# Project context

<Purpose and links to the tracker and relevant decisions.>

## Constraints and quirks

<Only facts a future contributor cannot cheaply infer from the code.>

## Language

**Experiment**: One candidate evaluation with its own result record.
```

Use only sections the project needs. Define overloaded project terms briefly;
prefer the project's established names over a skill's generic vocabulary.
Update stale facts when encountered. Promote an encountered issue into this
file only when it is a recurring constraint; a transient blocker stays with the
task, its plan, or its issue; never create per-attempt notes.

Preserve an existing multi-context layout and its `CONTEXT-MAP.md`; do not
introduce one merely to follow this template.
