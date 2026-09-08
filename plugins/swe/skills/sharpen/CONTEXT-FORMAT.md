# Project context

`docs/agents/CONTEXT.md` holds the small amount of reusable project knowledge
that a new session needs: purpose, terminology, non-obvious constraints, useful
quirks, and links to canonical documents. It lives behind the project's existing
gitignored `docs/agents/` symlink. Create it only when useful context exists.

Keep each fact in one home:

- `AGENTS.md`: verified repository commands and recurring work conventions.
- `CONTEXT.md`: project context and glossary; the tracker pin may live here when
  `AGENTS.md` is shared across repositories.
- Spec: approved intent, scope, design and acceptance criteria.
- Tracker: tasks, dependencies, ownership, progress and current blockers.
- ADR: a significant decision and the rationale needed to revisit it.

Link to those records instead of copying them. Personal preferences and agent
memory belong with the agent, not in project context. Do not keep an action
ledger, session transcript, or duplicate task status here.

## Optional shape

```md
# Project context

<Purpose and links to the relevant specs, tracker and decisions.>

## Constraints and quirks

<Only facts a future contributor cannot cheaply infer from the code.>

## Language

**Experiment**: One candidate evaluation with its own result record.
```

Use only sections the project needs. Define overloaded project terms briefly;
prefer the project's established names over a skill's generic vocabulary.
Update stale facts when encountered. Promote an encountered issue into this
file only when it is a recurring constraint; a transient blocker stays with the
task. One short handoff may retain unfinished work that cannot be reconstructed
cheaply, but it must not become a parallel journal.

Preserve an existing multi-context layout and its `CONTEXT-MAP.md`; do not
introduce one merely to follow this template.
