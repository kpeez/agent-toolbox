# Interface Design — Design It Twice

When the user wants to explore alternative interfaces for a chosen deepening
candidate, use this parallel sub-agent pattern. Based on **"Design It Twice"**
(Ousterhout): your first idea is unlikely to be the best, so design several
radically different interfaces in parallel and compare.

Uses the vocabulary in `SKILL.md` — **module**, **interface**, **seam**,
**adapter**, **depth/leverage** — and the dependency categories in `DEEPENING.md`.

## Process

### 1. Frame the problem space

Before spawning sub-agents, write a short user-facing explanation of the problem
space for the chosen candidate:

- The constraints any new interface must satisfy (invariants, ordering, error
  modes, performance — e.g. "must stay differentiable", "must run on one GPU",
  "rollout and update must not share mutable state").
- The dependencies it relies on and their category (see `DEEPENING.md`).
- A rough illustrative code sketch to ground the constraints — not a proposal,
  just a way to make them concrete.

Show this to the user, then immediately proceed. The user reads and thinks while
the sub-agents work.

### 2. Spawn sub-agents

Spawn 3+ sub-agents **in parallel** with the Agent tool. Each must produce a
**radically different** interface for the deepened module. Give each a separate
technical brief (file paths, coupling details, dependency category, what sits
behind the seam) and a different design constraint:

- Agent 1: **Minimize the interface** — 1–3 entry points max, maximum leverage per
  entry point.
- Agent 2: **Maximize flexibility** — support many use cases and extension points.
- Agent 3: **Optimize for the most common caller** — make the default case trivial.
- Agent 4 (if cross-seam deps): **Design around ports & adapters** for the
  remote-owned / true-external dependencies.

Include both the `SKILL.md` architecture vocabulary and the project's `CONTEXT.md`
domain vocabulary in each brief so agents name things consistently. Each sub-agent
outputs:

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
