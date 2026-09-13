---
name: sharpen
description: Stress-test a plan or design to resolve material ambiguity in scope, terminology, and acceptance criteria.
---

Resolve the questions that could materially change the goal, scope, design, or
acceptance criteria. Ask one question at a time and wait for its answer before
making dependent decisions; batch a small set of independent questions when
that reduces friction. Reuse decisions and approval already given; do not repeat
an interview when the requested work is clear.

If a question can be answered by exploring the codebase, explore
the codebase instead.

When recording glossary entries or ADRs, lead with the decision or term, keep
evidence close, and make consequences explicit.

When project-document updates are part of the request or established workflow,
use `docs/agents/` unless the project or user specifies another location. Create
subdirectories as needed, whether tracked or ignored, in an ordinary directory
or through an existing symlink.

## During the session

**Cross-check against the code.** Verify claims about behavior against the code.
Surface contradictions immediately and resolve which description is authoritative.

**Sharpen fuzzy language.** When a term is vague or overloaded, propose a precise
canonical one. If a `docs/agents/CONTEXT.md` glossary exists, check whether a
conflicting term reflects a real change. Record a pinned term in `CONTEXT.md`
only when it is reusable and the document update is within the request or
established workflow; otherwise keep it in the conversation or requested
artifact. See [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md).

**Discuss concrete scenarios when useful.** Use a specific edge case when it
forces precision about a material boundary; do not add examples when the code
and requirements already resolve the question.

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

Record an ADR only when **all three** conditions below are true and the request
or established workflow authorizes the document update:

1. **Hard to reverse** — the cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons

If any of the three is missing, skip it. When all three hold, record it
under `docs/agents/adrs/` using [ADR-FORMAT.md](./ADR-FORMAT.md), then tell me you did
and why.
