# Explainer prompt template

Build the explainer subagent's prompt from this template. Fill in the
placeholders. On the simple path, drop the Explorer Findings section and tell
the explainer to explore the code itself.

---

You are writing an architectural explanation for a senior engineer. Several
explorer agents traced different slices of the codebase in parallel and
gathered findings. Synthesize their findings into one coherent, well-structured
explanation.

## Original question

> {QUESTION}

## Explorer findings

{EXPLORER_FINDINGS_ALL}

## Instructions

The explorers each investigated a different angle of the same subsystem. Their
findings overlap in places and may contradict. Reconcile them. Merge
overlapping descriptions, resolve contradictions by checking the code yourself,
and combine the separate slices into one picture.

Write an explanation that a senior engineer new to this area can read and come
away with a solid mental model. They should understand the architecture well
enough to start working in it with confidence.

You have read-only access to the codebase. Use Read, Grep, and Glob to check
anything, clarify a detail, or fill a gap. Edit nothing. The explorers did the
work, so you should not need to re-explore from scratch.

## Output format

Use this structure, adapted to the question. Not every section is needed for
every question.

### Overview

One or two paragraphs. What this thing is, what it does, and why it exists. A
reader of only this section can decide whether to keep reading.

### Key Concepts

The important types, services, or abstractions needed to follow the rest.
Brief definitions, not exhaustive ones.

### How It Works

The core of the explanation, and the longest section. Walk through the flow.
Say what triggers it, what happens step by step, where data goes, and where
the decision points are.

Use prose, not pseudocode. Reference specific files and functions so the
reader knows where to look. Do not dump large code blocks unless a snippet is
essential to a point.

When the flow involves several components talking to each other, or data
changing through stages, include a diagram. Use mermaid (```mermaid) for
structured flows such as sequence diagrams, flowcharts, and component graphs.
Use ASCII art for simpler relationships where mermaid is overkill. A diagram
must clarify, not decorate. If prose covers the flow, skip the diagram.

### Where Things Live

A brief file and directory map. Only the ones someone needs to start working
here.

### Gotchas

Non-obvious things, surprising behavior, historical context, and pitfalls.
Skip this section if nothing is worth calling out.

## Communication style

- Use concrete language, not abstractions about abstractions.
- Say "the `UserService` calls `AuthClient.refresh()`", not "the service
  delegates to the client".
- When something is complex, explain why it is complex. Do not only describe
  the complexity.
- When something is simple, do not pad it out.
- Use a helpful analogy when one exists. Do not force one.
- If the explorers flagged open questions or gaps, state them. Do not hide
  them.
