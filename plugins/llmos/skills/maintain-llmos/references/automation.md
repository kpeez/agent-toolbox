---
status: active
authors:
  - codex
  - claude
created: 2026-07-15
updated: 2026-07-16
---

# Scheduled review lifecycle

Two active local Codex automations maintain llmOS:

- `llmOS nightly daily closeout` at 23:30 local time every day.
- `llmOS Sunday weekly synthesis` at 23:50 local time each Sunday.

The daily run verifies the vault: the metadata, Base, backlink, Obsidian, qmd, skill, secret, Git, and commit checks. It has no branch to close — routine work commits straight to `main` — so it audits state, repairs what it can, and reports what it cannot. A quiet day is a valid state, not a failure: run the verification, report what landed, exit clean.

What *is* a signal is a branch that has merged nowhere and is no longer being worked. Report it; never delete it, never force-merge it.

The `## Projects` digest that fills `reviews/daily/YYYY-MM-DD.md` is **not** this agent's job. It is a separate scheduled script — fetch, hash, one model call, write — precisely so it cannot drift, half-finish, or decide to do something else. It processes both today and yesterday on each run, because an evening pass cannot see work that lands after it.

The weekly run starts only after Sunday's daily closeout. It writes `reviews/weekly/YYYY-Www.md`, synthesizing the week's daily notes, repairing contradictions or missing connections, promoting reusable knowledge and skills, and verifying the vault. Like the daily note, the synthesis is generated prose committed to `main` — there is no week branch and nothing to squash.

Both runs skip pushing when `origin` is absent. Neither may force-push, discard work, or merge after a failed check.

See also: [[projects/llmos/adrs/0008-commit-to-main-and-branch-only-for-review|Commit to main; branch only for review]]
