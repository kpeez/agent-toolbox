# Review details

Details for [review mode](../SKILL.md#review-mode). Use the vocabulary and key
tests in [SKILL.md](../SKILL.md#vocabulary).

The project's domain model can inform the review. Consult a
`.agents/docs/CONTEXT.md` glossary or relevant `.agents/docs/adrs/` when it
bears on the friction or recommendation. Use its rationale to compare options.
Follow an explicit project or user override of the `.agents/docs/` location.
Do not require a document preflight for every review.

## 1-explore-friction

Start with the requested area and its callers. Walk the codebase, delegating
bounded breadth when useful. Do not follow rigid heuristics. Note where you
experience friction:

- Where does understanding one concept require bouncing between many small modules?
- Where are modules **shallow** — interface nearly as complex as the implementation?
- Where have pure functions been extracted just for testability, but the real bugs hide in how they're called?
- Where do tightly-coupled modules leak across their seams?
- Which parts are untested, or hard to test through their current interface?

Apply the **deletion test** to anything you suspect is shallow.

## 3-report-candidates

Default output is a **markdown report**: concise, conclusion first, evidence
close to claims, in the chat or a scratch file, not committed to the repo. This
review proposes changes; it does not authorize implementation. For each
candidate:

- **Files** — which modules are involved
- **Problem** — why the current architecture causes friction
- **Solution** — plain-English description of what would change
- **Benefits** — in terms of leverage (what callers gain) and locality (change/bugs/knowledge concentrated in one place), and how tests improve
- **Before / After** — a short sketch of the shallow shape vs the deepened one
- **Strength** — `Strong` | `Worth exploring` | `Speculative`

Use `CONTEXT.md` vocabulary for the domain and the vocabulary in
[SKILL.md](../SKILL.md#vocabulary) for the architecture. Decision records
explain earlier choices; they do not forbid alternatives. Rank candidates by
current goals, evidence, constraints, and switching costs, without penalizing
disagreement with an ADR. Explain the earlier rationale and why a different
choice would be better; its assumptions need not have changed. Verify any
claimed constraint at its current source. Recommending a change does not
authorize implementing it.

End with a **Top recommendation**: which you would tackle first and why. If no
candidate shows real caller friction and a net gain, say that no refactor is
recommended. If the choice is genuinely unresolved, ask which candidate to
explore; otherwise follow the requested depth. Keep a review-only request at
the report, and propose interfaces only when the user asks for design or has
chosen a candidate. A bounded worker reports the choice to its caller.

## 4-grill-chosen-design

When the user picks a candidate or asks for a specific candidate design, drop
into a grilling session with [grill](../../grill/SKILL.md). Walk the design
tree: constraints, dependencies, the shape of the deepened module, what sits
behind the seam, and what tests survive. Keep documentation side effects
conditional on the requested design workflow:

- If a chosen design introduces a reusable concept not in `CONTEXT.md`, record
  the term only when project-document updates are in scope (see the
  [context format](../../../references/CONTEXT-FORMAT.md)).
- If the user rejects a candidate for a load-bearing reason a future review would
  re-suggest, consider an ADR only when all three
  [decision-record criteria](../../../references/ADR-FORMAT.md) hold and the
  document update is in scope. Skip ephemeral ("not worth it right now") and
  self-evident reasons.

When a candidate is chosen for design, classify its dependencies and pick the
test seam with [deepening](deepening.md) (in-process / local-substitutable /
remote-owned ports-&-adapters / true-external). Treat the categories as
heuristics for what to merge, substitute, or mock. Do not implement the
candidate unless that work is separately authorized.

If the right interface for a chosen candidate is non-obvious, use the shared
[interface-design procedure](interface-design.md) to frame constraints and
compare materially different interfaces. Generate alternatives directly for a
bounded design, or delegate independent alternatives when the added breadth is
worth the cost.

In a standalone task, delegate heavy exploration when useful, then review the
evidence and recommendation. A bounded worker reports to its caller.
