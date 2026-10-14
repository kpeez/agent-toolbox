# Decision records (ADRs)

Write an ADR only when a decision is all three: hard to reverse, surprising to
a later reader, and the result of a real trade-off. Skip the others.

Store it at `.agents/docs/adrs/NNNN-slug.md`, one number above the highest
existing one, unless the project or user names another place. Follow the
project's own frontmatter when it has one; otherwise:

```md
---
status: accepted
decided_on: YYYY-MM-DD
---

# <Short title>

<1-3 sentences: what was chosen, for which scope, and why.>
```

Add "Considered options" or "Consequences" only when they help a later reader.

To replace a decision, set the old record to `status: superseded` with
`superseded_by: <path>`. Keep its text.

An ADR is history, not a rule. Check a requirement at its current source, and
replace a past choice when the evidence is better.
