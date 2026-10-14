# Explorer prompt template

Build each explorer subagent's prompt from this template. Fill in the
placeholders.

---

Other explorers are investigating different slices of the same subsystem in
parallel. Do not try to cover everything. Focus on your assigned angle and go
deep. Read only. Edit nothing.

## Question

> {QUESTION}

## Your exploration angle

{EXPLORATION_ANGLE}

## Output

### Components Found

The key types, services, classes, and abstractions. For each, give the name,
the file path, and one sentence on what it does.

### Flow

The execution flow, step by step. For each step, give the function or method
that runs, its file, what it does, and what it calls next. Include the data
that flows between steps.

### Files Read

Every file you read during exploration, so the explainer can reference them.

### Boundaries

Where this subsystem connects to other parts of the codebase. The inputs and
outputs.

### Non-Obvious Things

Anything surprising, historically motivated, or easy to get wrong. Things that
look like they work one way but work another.

### Open Questions

Anything you could not fully trace or understand. Be honest about gaps.
