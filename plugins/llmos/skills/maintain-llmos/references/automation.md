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

The daily run audits the day's catch-all branch `YYYY-MM-DD` and its per-spec children `<agent>/YYYY-MM-DD/<spec>`, discovers existing `projects/<project>/logs/YYYY-MM-DD-*.md`, and compares those spec-completion receipts with Git/session evidence. It confirms every per-spec branch has merged into the day's catch-all, runs the metadata, Base, backlink, Obsidian, qmd, skill, secret, Git, and commit checks, then squash-merges the catch-all into `main` as one dated commit.

The weekly run starts only after Sunday's daily closeout. It creates `weekly/YYYY-Www`, synthesizes the project logs directly for receipt-level evidence, repairs contradictions or missing connections, promotes reusable knowledge and skills, verifies the vault, and squash-merges the week into `main`.

Both runs skip pushing when `origin` is absent. Neither may force-push, discard work, or merge after a failed check.

See also: [[projects/llmos/docs/adrs/0002-use-daily-branches-and-nightly-squash-merges|Cascading branches and nightly squash merges]]
