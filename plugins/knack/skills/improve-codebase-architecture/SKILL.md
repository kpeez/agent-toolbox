---
name: improve-codebase-architecture
description: Find deepening opportunities in a codebase — refactors that turn shallow modules into deep ones, for testability and AI-navigability. Use when the user wants to improve architecture, find refactoring opportunities, consolidate tightly-coupled modules, or make a codebase easier to test and navigate.
---

# Improve Codebase Architecture

Surface architectural friction and propose **deepening opportunities** — refactors
that turn shallow modules into deep ones. The aim is testability and
AI-navigability.

## Vocabulary

Use these terms exactly in every suggestion — don't drift into "component,"
"service," "API," or "boundary." Consistent language is the point.

- **Module** — anything with an interface and an implementation (function, class, package, slice).
- **Interface** — everything a caller must know to use the module: types, invariants, error modes, ordering, required config, performance characteristics. Not just the type signature.
- **Implementation** — the code inside.
- **Depth** — leverage at the interface: a lot of behaviour behind a small interface. **Deep** = high leverage. **Shallow** = interface nearly as complex as the implementation.
- **Seam** — where an interface lives; a place behaviour can be altered without editing in place. (Use this, not "boundary.")
- **Adapter** — a concrete thing satisfying an interface at a seam.

Key principles:

- **Deletion test** — imagine deleting the module. If complexity vanishes, it was a pass-through. If complexity reappears across N callers, it was earning its keep.
- **The interface is the test surface.**
- **One adapter = hypothetical seam. Two adapters = real seam.**

This skill is *informed* by the project's domain model: the `CONTEXT.md` glossary
(if present) gives names to good seams; `docs/adr/` records decisions the skill
should not re-litigate.

## Process

### 1. Explore

Read `CONTEXT.md` and any `docs/adr/` in the area first. Then walk the codebase
(use the `Explore` subagent for breadth). Don't follow rigid heuristics — note
where you experience friction:

- Where does understanding one concept require bouncing between many small modules?
- Where are modules **shallow** — interface nearly as complex as the implementation?
- Where have pure functions been extracted just for testability, but the real bugs hide in how they're called?
- Where do tightly-coupled modules leak across their seams?
- Which parts are untested, or hard to test through their current interface?

Apply the **deletion test** to anything you suspect is shallow.

### 2. Present candidates

Default output is a **markdown report** (concise, in the chat or a scratch file —
not committed to the repo). For each candidate:

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

End with a **Top recommendation**: which you'd tackle first and why. Then ask the
user which to explore. Do NOT propose interfaces yet.

> Optional: if the user asks for something more visual, render the same content as
> a self-contained HTML file in the OS temp dir (Tailwind + Mermaid via CDN) and
> open it — but markdown is the default; don't reach for HTML unless asked.

### 3. Grilling loop

Once the user picks a candidate, drop into a grilling conversation (`/grill-me`).
Walk the design tree — constraints, dependencies, the shape of the deepened
module, what sits behind the seam, what tests survive. Side effects happen inline:

- Naming a deepened module after a concept not in `CONTEXT.md`? Add the term
  (see `grill-me`'s `CONTEXT-FORMAT.md`).
- The user rejects a candidate for a load-bearing reason a future review would
  re-suggest? Offer an ADR (see `grill-me`'s `ADR-FORMAT.md`). Skip ephemeral
  ("not worth it right now") and self-evident reasons.
