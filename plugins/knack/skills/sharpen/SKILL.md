---
name: sharpen
description: Interview the user relentlessly about a plan or design until reaching shared understanding, resolving each branch of the decision tree. Cross-checks claims against the code, sharpens terminology, and records durable decisions as ADRs. Use when the user wants to stress-test, pressure-test, or harden a plan or design, or mentions "sharpen", /sharpen, or "grill me".
disable-model-invocation: true
---

Interview me relentlessly about every aspect of this plan until
we reach a shared understanding. Walk down each branch of the design
tree resolving dependencies between decisions one by one. Ask the questions one at a time, waiting for feedback on each question before continuing.

If a question can be answered by exploring the codebase, explore
the codebase instead.

When recording glossary entries or ADRs, lead with the decision or term, keep
evidence close, and make consequences explicit.

## During the session

**Cross-check against the code.** When I state how something works, verify the
code agrees. If you find a contradiction, surface it immediately: "Your code
cancels entire Orders, but you just said partial cancellation is possible — which
is right?"

**Sharpen fuzzy language.** When I use a vague or overloaded term, propose a
precise canonical one. "You're saying 'account' — do you mean the Customer or the
User? Those are different things." If a repo-root `CONTEXT.md` glossary exists,
challenge any term that conflicts with it. When a term gets pinned down, capture
it in `CONTEXT.md` right there — see [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md).
Create the file lazily, only when the first term is resolved.

**Discuss concrete scenarios.** Stress-test domain relationships with specific
edge-case scenarios that force precision about the boundaries between concepts.

**Escalate close calls to `/deliberate`.** When a decision reduces to two named
options or a yes/no, don't argue it inline — invoke `/deliberate` to commission
the two cases, then fold the synthesis back into the interview.

## Recording decisions as ADRs

Record an ADR only when **all three** are true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip it. When all three hold, record it via the
`docs/adrs/` symlink using [ADR-FORMAT.md](./ADR-FORMAT.md), then tell me you did
and why. ADRs live in the shared llmOS vault, not the repo; if the `docs/adrs/`
symlink is missing, run `/setup-repo` to establish the approved project-docs
topology first.
