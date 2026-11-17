---
name: how
description: "Explain how code works now: a subsystem's architecture, its runtime flow, or a walkthrough before you change it. Also for placement, ownership, and layering questions such as 'where should this live'. Use why for motivation."
argument-hint: "<subsystem or question>"
disable-model-invocation: true
---

# How

Answer "how does X work?" questions. When the scope is ambiguous, state your
reading and explore. The user can redirect.

## 1. Explain

Start one fresh read-only subagent that explores and explains in one pass.
Give it the user's question and this brief:

> You write an architectural explanation for a senior engineer. Explore the
> codebase. Write an explanation that a senior engineer who does not know
> this area can read to get a solid mental model, good enough to start work
> in it with confidence. You have read-only access to the codebase.

## 2. Present

Present the subagent's output. Light edits for clarity or for context from
the conversation are fine. Do not substantially rewrite it.
