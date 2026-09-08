# Interface Design — Design It Twice

When a chosen deepening candidate has a consequential, non-obvious interface,
compare materially different designs before committing. Parallel subagents can
help with a broad design, but are not required.

Uses the vocabulary in `SKILL.md` — **module**, **interface**, **seam**,
**adapter**, **depth/leverage** — and the dependency categories in `DEEPENING.md`.

## Process

### 1. Frame the problem space

Before generating alternatives, write a short explanation of the problem space
for the chosen candidate:

- The constraints any new interface must satisfy (invariants, ordering, error
  modes, performance — e.g. "must stay differentiable", "must run on one GPU",
  "rollout and update must not share mutable state").
- The dependencies it relies on and their category (see `DEEPENING.md`).
- A rough illustrative code sketch to ground the constraints — not a proposal,
  just a way to make them concrete.

In an interactive standalone task, show this to the user when their feedback
could materially change the design. A bounded worker reports the frame to its
caller.

### 2. Generate alternatives

Generate the smallest useful set of materially different interfaces. Do this
directly for a bounded design, or delegate independent alternatives when the
codebase breadth or decision cost justifies it. Useful design constraints
include:

- **Minimize the interface** — the smallest caller surface that meets the goal.
- **Support known variation** — accommodate the required use cases without
  hypothetical extension points.
- **Optimize for the most common caller** — make the default case trivial.
- **Design around ports & adapters** when cross-seam dependencies justify it.

When delegating, include relevant file paths, coupling details, dependency
categories, what sits behind the seam, and the project's established domain
language. Each alternative covers:

1. Interface — types, methods, params, plus invariants, ordering, error modes
2. A usage example showing how callers use it
3. What the implementation hides behind the seam
4. Dependency strategy and adapters (see `DEEPENING.md`)
5. Trade-offs — where leverage is high, where it's thin

### 3. Present and compare

Present the designs sequentially so the user can absorb each, then compare them in
prose by **depth** (leverage at the interface), **locality** (where change
concentrates), and **seam placement**. Give your own opinionated recommendation —
which is strongest and why. If elements from different designs combine well,
propose a hybrid. The user wants a strong read, not a menu.
