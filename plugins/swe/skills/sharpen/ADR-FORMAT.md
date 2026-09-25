# Decision history (ADR format)

An ADR records what was chosen and why, not what future work must choose.

Store ADRs under `.agents/docs/adrs/` unless the project or user specifies another
location. Create the directory as needed; it may be tracked, ignored, or reached
through an existing symlink.

Within `.agents/docs/adrs/`, ADRs use sequential numbering: `0001-slug.md`,
`0002-slug.md`, etc.

## Template

```md
---
status: accepted
decided_on: YYYY-MM-DD
---

# {Short title of the decision}

{1-3 sentences: what did we choose, for which scope and assumptions, and why?}
```

That's it. An ADR can be a single paragraph. The value is in recording _that_ a decision was made and _why_ — not in filling out sections.

## Optional sections

Only include these when they add genuine value. Most ADRs won't need them.

- **Considered Options** — only when the rejected alternatives are worth remembering
- **Consequences** — only when non-obvious downstream effects need to be called out

## Status and applicability

Use one `status` field: `proposed`, `accepted`, `deprecated`, or `superseded`.
`accepted` means the choice was made at the recorded time, not that it is a
permanent requirement. Record the actual decision date; if it cannot be recovered
for an older decision, say it is unknown rather than inventing one.
When a decision is replaced, set `status: superseded`, add `superseded_by` with
the replacement document's relative path, and add a short dated note explaining
what changed. Use `deprecated` when the decision no longer applies and has no
replacement. Preserve the original context, alternatives and reasoning.

Evaluate alternatives against current goals, evidence, constraints, and switching
costs. Neither agreement nor disagreement with an ADR determines an option's
merit. The prior assumptions need not have changed for a better option to exist.
Use the earlier reasoning to avoid repeating mistakes, not to suppress proposals.

Distinguish decision history from current constraints and permission to act.
Verify a claimed requirement at its current source, such as an explicit user
instruction or compatibility contract. If its applicability is uncertain and
material, resolve that uncertainty rather than silently dropping it.
Within an authorized task, a justified replacement needs no approval merely
because an ADR exists. Changing explicit requirements or approved plan intent,
or exceeding the task's scope, still needs the applicable approval. Explain
what the earlier choice optimized for and why the replacement is better.

A missing status on an older record does not establish current authority.
For a partial replacement, say which portion is superseded and which remains
applicable. Do not rewrite unrelated records or silently erase old decisions.

## Numbering

Scan `.agents/docs/adrs/` for the highest existing number and increment by one.

## When to offer an ADR

All three of these must be true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will look at the code and wonder "why on earth did they do it this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons

If a decision is easy to reverse, skip it — you'll just reverse it. If it's not surprising, nobody will wonder why. If there was no real alternative, there's nothing to record beyond "we did the obvious thing."

### What qualifies

- **Architectural shape.** "We're using a monorepo." "The write model is event-sourced, the read model is projected into Postgres."
- **Integration patterns between contexts.** "Ordering and Billing communicate via domain events, not synchronous HTTP."
- **Technology choices that carry lock-in.** Database, message bus, auth provider, deployment target. Not every library — just the ones that would take a quarter to swap out.
- **Boundary and scope decisions.** "Customer data is owned by the Customer context; other contexts reference it by ID only." The explicit no-s are as valuable as the yes-s.
- **Deliberate deviations from the obvious path.** "We chose manual SQL instead of an ORM because X." Preserve the trade-off so the next engineer can evaluate it.
- **Decisions shaped by external constraints.** Record how a compliance rule or partner contract affected the choice, linking to the requirement's source so its current applicability can be checked.
- **Rejected alternatives when the rejection is non-obvious.** Record why REST was preferred over GraphQL so future comparisons can use that evidence, not to prevent another comparison.
