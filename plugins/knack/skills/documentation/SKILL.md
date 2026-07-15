---
name: documentation
description: Write clear, reviewable Markdown documentation for specs, issues, PRs, ADRs, READMEs, guides, experiment reports, model and dataset notes, architecture reports, and handoffs. Use when any skill or agent creates durable documentation, issue bodies, spec text, PR descriptions, decision records, or research summaries.
user-invocable: false
---

# Documentation

Write documentation that helps a future reader decide, implement, review, or
resume work. Prefer plain Markdown that renders well in GitHub, editors, issue
trackers, and docs sites.

## Default Shape

1. Start with the conclusion, decision, or requested action.
2. Explain the problem and context only as much as the reader needs.
3. Put evidence close to the claim it supports.
4. Make scope boundaries explicit.
5. End with verification, open questions, or handoff state when relevant.

Use the project's own vocabulary from `CONTEXT.md` and respect `docs/adr/`.
Do not invent presentation systems or custom markup.

## References

Read [references/markdown-patterns.md](references/markdown-patterns.md) before
writing specs, issues, PR bodies, ADRs, README sections, architecture reports,
handoffs, or other durable Markdown.
