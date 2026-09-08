---
name: sharpen
description: Resolve material ambiguity in a plan or design through focused questions and code evidence. Sharpen terminology and record significant decisions. Use when the user wants to stress-test, pressure-test, or harden a plan or design, or mentions "sharpen", /sharpen, or "grill me".
---

Resolve the questions that could materially change the goal, scope, design, or
acceptance criteria. Ask one question at a time and wait for its answer before
making dependent decisions. Reuse decisions and approval already given; do not
repeat an interview when the requested work is clear.

If a question can be answered by exploring the codebase, explore
the codebase instead.

When recording glossary entries or ADRs, lead with the decision or term, keep
evidence close, and make consequences explicit.

Use `docs/agents/` for project documents unless the project or user specifies
another location. Create subdirectories as needed, whether tracked or ignored,
in an ordinary directory or through an existing symlink.

## During the session

**Cross-check against the code.** When I state how something works, verify the
code agrees. If you find a contradiction, surface it immediately: "Your code
cancels entire Orders, but you just said partial cancellation is possible — which
is right?"

**Sharpen fuzzy language.** When I use a vague or overloaded term, propose a
precise canonical one. "You're saying 'account' — do you mean the Customer or the
User? Those are different things." If a `docs/agents/CONTEXT.md` glossary exists,
check whether a conflicting term reflects a real change. When a term gets pinned down, capture
it in `CONTEXT.md` right there — see [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md).
Create the file only when there is reusable project context to retain.

**Discuss concrete scenarios.** Stress-test domain relationships with specific
edge-case scenarios that force precision about the boundaries between concepts.

**Deliberate close calls.** Compare the plausible alternatives against concrete
requirements and evidence. Delegate bounded evidence gathering when substantial
reads would crowd the lead's context. Do not manufacture competing cases or
extra agents for a decision the available evidence already resolves. Explain
the trade-off and recommend an option; insufficient evidence is a valid result.

**Check decision freshness.** Read relevant ADRs for rationale, then check their
status and applicability against current code and user intent. Surface material
conflicts instead of silently following or replacing an obsolete decision. Use
the status convention in [ADR-FORMAT.md](./ADR-FORMAT.md) when a decision changes.

## Recording decisions as ADRs

Record an ADR only when **all three** are true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip it. When all three hold, record it
under `docs/agents/adrs/` using [ADR-FORMAT.md](./ADR-FORMAT.md), then tell me you did
and why.
