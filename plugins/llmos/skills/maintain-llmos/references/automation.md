---
status: active
authors:
  - codex
created: 2026-07-15
updated: 2026-07-15
categories:
  - "[[agents/Agent infrastructure]]"
topics:
  - "[[Agent workflows]]"
---

# Scheduled review lifecycle

Two active local Codex automations maintain llmOS:

- `llmOS nightly daily closeout` at 23:30 local time every day.
- `llmOS Sunday weekly synthesis` at 23:50 local time each Sunday.

The daily run audits the day's catch-all branch `YYYY-MM-DD` and its per-spec children `<agent>/YYYY-MM-DD/<spec>`. It confirms every per-spec branch has merged into the day's catch-all, runs the metadata, Base, backlink, Obsidian, qmd, skill, secret, Git, and commit checks, then squash-merges the catch-all into `main` as one dated commit.

The `## Projects` digest that fills `reviews/daily/YYYY-MM-DD.md` is **not** this agent's job. It is a separate scheduled script — fetch, hash, one model call, write — precisely so it cannot drift, half-finish, or decide to do something else. It processes both today and yesterday on each run, because an evening pass cannot see work that lands after it.

The weekly run starts only after Sunday's daily closeout. It creates `weekly/YYYY-Www`, synthesizes the week's daily notes, repairs contradictions or missing connections, promotes reusable knowledge and skills, verifies the vault, and squash-merges the week into `main`.

Both runs skip pushing when `origin` is absent. Neither may force-push, discard work, or merge after a failed check.

See also: [[projects/llmos/adrs/0002-use-daily-branches-and-nightly-squash-merges|Cascading branches and nightly squash merges]]
