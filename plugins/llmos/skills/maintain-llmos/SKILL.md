---
name: maintain-llmos
description: Maintain the shared llmOS Obsidian vault. Use when an agent files or retrieves durable knowledge, updates project docs or specs, writes daily or weekly reviews, migrates documents into llmOS, repairs links or properties, or extracts a recurring workflow into a shared skill.
---

# Maintain llmOS

Treat llmOS as the canonical shared store. Keep only provider-native memory and routing under `agents/<provider>/`; keep reusable knowledge shared. Canonical project specifications and ADRs live under `projects/<project>/docs/specs/` and `projects/<project>/docs/adrs/`.

## Workflow

1. Resolve the vault from `LLMOS_ROOT`, or use the current Git root when it contains `.obsidian/` and `AGENTS.md`.
2. Read `[[llmOS]]`, `AGENTS.md`, and the nearest area or canonical project note/landing page with `obsidian-cli vault="llmOS" read path="..."`.
3. Delegate broad exploration to a bounded subagent. Keep synthesis and cross-cutting decisions with the primary agent.
4. Use `qmd search -c llmos` for exact retrieval or `qmd query -c llmos` for semantic and cross-note retrieval. Fetch full hits with `qmd get` before using them.
5. Classify linked `categories`, linked `topics`, and linked `project` (omitting empty properties), then file the result with the matching template using [the schema and directory map](references/schema.md).
6. Add the current provider to `authors` without removing prior authors, and bump `updated`. This is manual — no hook stamps frontmatter.
7. Write a receipt only when a spec is completed — all its required child issues in a published implementation cycle are implemented. Spec drafting, issue publication, and intermediate issue completion do not warrant a receipt. Call `<llmos-plugin-root>/scripts/write_daily_receipt.py` with a stable `--receipt-id` (the spec slug) and exactly two fields:

   - `--desc`: what the implemented spec does.
   - `--info`: backlinks to the spec, plans, local issues, and PRs (repeatable).

   The writer always routes to `projects/<slug>/logs/YYYY-MM-DD-<slug>.md`, taking `--project <slug>` or inferring it from the working repo's basename. Re-running with the same `--receipt-id` is idempotent. Do not copy the transcript.
8. Verify changed notes through Obsidian CLI. Query changed Base views, confirm project backlinks, run `<llmos-plugin-root>/scripts/audit_metadata.py`, check unresolved links, update qmd, retrieve a representative full note, and review Git status.

## Promote recurring patterns

When a workflow or hard-won lesson will recur across projects or providers, create or update a focused sibling skill in this plugin during the same task. Skills live in the agent-toolbox plugins, never in the vault — the vault holds notes. Use the skill creator, keep instructions concise, put deterministic behavior in scripts, and run `quick_validate.py`.

## Scripts

Record a spec completion:

```sh
python3 "<llmos-plugin-root>/scripts/write_daily_receipt.py" \
  --agent codex \
  --receipt-id llmos-project-daily-logs \
  --desc "Route spec-completion receipts to per-project dated logs" \
  --info "[[spec-llmos-project-daily-logs]], #1 #2 #3, PR #7" \
  --project llmos
```

Manage the cascading branch model — `main` <- `YYYY-MM-DD` (catch-all) <- `<agent>/YYYY-MM-DD/<spec>`:

```sh
python3 "<llmos-plugin-root>/scripts/daily_branch.py" start                              # today's catch-all, off main
python3 "<llmos-plugin-root>/scripts/daily_branch.py" spec --agent codex --name my-spec  # per-spec branch, off the catch-all
```

Receipts always land in `projects/<project>/logs/YYYY-MM-DD-<project>.md`; there is no projectless route and no frontmatter-stamping hook. The scripts use only the Python standard library and write plain files — no Obsidian CLI dependency.

Use `<llmos-plugin-root>/scripts/audit_metadata.py` for a schema audit; it is read-only unless you pass `--fix`.

Every canonical spec (`projects/<project>/docs/specs/NNNN-<slug>.md`) carries the minimal `Specifications` category and project ownership. Both are implied by the file's own path, so `--fix` stamps them rather than any agent hand-typing them — run it after `/write-spec` creates a spec, since that command is vault-agnostic and writes only the workflow properties (`status`, `desc`, `blocked`). Legacy supporting notes may remain unclassified until materially edited.
