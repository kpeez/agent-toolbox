# ADR Format

ADRs are **committed** to `docs/adr/` in the repo (not the private `specs/`
tree) so they survive a fresh clone and stop the next person — or the next agent
— from re-litigating a settled decision. Sequential numbering: `0001-slug.md`,
`0002-slug.md`. Create `docs/adr/` lazily, only when the first ADR is needed.

Scan `docs/adr/` for the highest existing number and increment by one.

## Template

```md
# {Short title of the decision}

{1-3 sentences: what's the context, what did we decide, and why.}
```

That's it. An ADR can be a single paragraph. The value is in recording *that* a
decision was made and *why* — not in filling out sections.

## Optional sections

Only include these when they add genuine value. Most ADRs won't need them.

- **Status** frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`) — useful when decisions are revisited
- **Considered Options** — only when the rejected alternatives are worth remembering
- **Consequences** — only when non-obvious downstream effects need calling out

## When to write one

All three must be true (see `SKILL.md`): hard to reverse, surprising without
context, the result of a real trade-off. Things that qualify:

- **Architectural shape** — "the write model is event-sourced, read model projected into Postgres."
- **Technology choices with lock-in** — database, message bus, auth provider, deployment target, ML framework/training stack. Not every library — just the ones that would take a quarter to swap.
- **Boundary and scope decisions** — what a module owns, and the explicit no-s.
- **Deliberate deviations from the obvious path** — "manual SQL instead of an ORM because X." Anything a reasonable reader would assume the opposite of. Stops the next engineer from "fixing" something deliberate.
- **Constraints not visible in the code** — compliance, latency budgets, a partner API contract, a dataset licensing limit.
- **Rejected alternatives when the rejection is non-obvious** — considered approach Y, picked X for subtle reasons; record it or someone suggests Y again in six months.

For ML/research repos specifically: the experiment direction you tried and
abandoned (with the reason) is exactly what an ADR is for — it stops a future
session from burning compute re-running a dead end.
