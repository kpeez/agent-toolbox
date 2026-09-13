---
name: improve-codebase-architecture
description: Review existing module boundaries and propose refactors that reduce coupling or caller complexity.
---

# Improve Codebase Architecture

Surface architectural friction and propose **deepening opportunities** — refactors
that turn shallow modules into deep ones. The aim is testability and
AI-navigability.

## Vocabulary

Use the `codebase-design` vocabulary
([../codebase-design/SKILL.md](../codebase-design/SKILL.md)) when it makes the
review clearer: module, interface, depth, seam, adapter, deletion test, and
interface-as-test-surface. Use the project's established terms where they are
clearer. Read that skill only when the distinction matters to the review.

This skill can be informed by the project's domain model: consult a
`docs/agents/CONTEXT.md` glossary or relevant `docs/agents/adrs/` when it bears
on the friction or recommendation. Check whether an ADR still applies before
relying on it. Follow an explicit project or user override of the
`docs/agents/` location.

## Process

### 1. Explore

Start with the requested area and its callers. Consult project context or ADRs
when they clarify the domain or a decision that bears on the friction; do not
require a document preflight for every review. Walk the codebase, delegating
bounded breadth when useful. Don't follow rigid heuristics — note where you
experience friction:

- Where does understanding one concept require bouncing between many small modules?
- Where are modules **shallow** — interface nearly as complex as the implementation?
- Where have pure functions been extracted just for testability, but the real bugs hide in how they're called?
- Where do tightly-coupled modules leak across their seams?
- Which parts are untested, or hard to test through their current interface?

Apply the **deletion test** to anything you suspect is shallow.

### 2. Present candidates

Default output is a **markdown report** — concise, conclusion first, evidence
close to claims, in the chat or a scratch file, not committed to the repo. This
review proposes changes; it does not authorize implementation. For
each candidate:

- **Files** — which modules are involved
- **Problem** — why the current architecture causes friction
- **Solution** — plain-English description of what would change
- **Benefits** — in terms of leverage (what callers gain) and locality (change/bugs/knowledge concentrated in one place), and how tests improve
- **Before / After** — a short sketch of the shallow shape vs the deepened one
- **Strength** — `Strong` | `Worth exploring` | `Speculative`

Use `CONTEXT.md` vocabulary for the domain and the terms above for the
architecture. If a candidate contradicts an existing ADR, only surface it when
the friction is real enough to warrant reopening the ADR, and mark it clearly
(_"contradicts ADR-0007 — but worth reopening because…"_). Don't list every
refactor an ADR forbids.

End with a **Top recommendation**: which you'd tackle first and why. If the
choice is genuinely unresolved, ask which candidate to explore; otherwise follow
the requested depth. Keep a review-only request at the report, and propose
interfaces only when the user asks for design or has chosen a candidate. A
bounded worker reports the choice to its caller.

> Optional: if the user asks for something more visual, render the same content as
> a self-contained HTML file in the OS temp dir (Tailwind + Mermaid via CDN) and
> open it — but markdown is the default; don't reach for HTML unless asked.

### 3. Sharpen chosen designs

When the user picks a candidate or asks for a specific candidate design, drop
into a sharpening conversation (`/sharpen`). Walk the design tree — constraints,
dependencies, the shape of the deepened module, what sits behind the seam, and
what tests survive. Keep documentation side effects conditional on the requested
design workflow:

- If a chosen design introduces a reusable concept not in `CONTEXT.md`, record
  the term only when project-document updates are in scope (see `sharpen`'s
  `CONTEXT-FORMAT.md`).
- If the user rejects a candidate for a load-bearing reason a future review would
  re-suggest, offer an ADR (see `sharpen`'s `ADR-FORMAT.md`). Skip ephemeral
  ("not worth it right now") and self-evident reasons.

When a candidate is chosen for design, classify its dependencies and pick the
test seam with **`DEEPENING.md`** (in-process / local-substitutable / remote-owned
ports-&-adapters / true-external). Treat the categories as heuristics for what
to merge, substitute, or mock. Do not implement the candidate unless that work
is separately authorized.

### 4. Compare alternatives when useful

If the right interface for a chosen candidate is non-obvious, use
**`INTERFACE-DESIGN.md`** to frame constraints and compare materially different
interfaces. Generate alternatives directly for a bounded design or delegate
independent alternatives when the added breadth is worth the cost.

> In a standalone task, delegate heavy exploration when useful, then review the
> evidence and recommendation. A bounded worker reports to its caller.
