---
name: maintain-llmos
description: Maintain the shared llmOS Obsidian vault. Use when an agent files or retrieves durable knowledge, updates project docs or specs, writes daily or weekly reviews, migrates documents into llmOS, repairs links or properties, or extracts a recurring workflow into a shared skill.
---

# Maintain llmOS

Treat llmOS as the canonical shared store; keep reusable knowledge shared. No provider writes memory into the vault (ADR-0003) — `agents/` holds only `references/`. Canonical project specifications and ADRs live under `projects/<project>/specs/` and `projects/<project>/adrs/`.

## Workflow

1. Resolve the vault with `<llmos-plugin-root>/scripts/vault_root.py`. Never derive it from the working directory or a file's location (ADR-0001).
2. Read `[[llmOS]]`, `AGENTS.md`, and the nearest area or canonical project note/landing page with `obsidian-cli vault="llmOS" read path="..."`.
3. Delegate broad exploration to a bounded subagent. Keep synthesis and cross-cutting decisions with the primary agent.
4. Use `qmd search -c llmos` for exact retrieval or `qmd query -c llmos` for semantic and cross-note retrieval. Fetch full hits with `qmd get` before using them.
5. Classify linked `categories`, linked `topics`, and linked `project` (omitting empty properties), then file the result with the matching template using the schema and directory map at `$LLMOS_ROOT/agents/references/schema.md`, which the vault single-sources (ADR-0002).
6. The PostToolUse format+stamp hook appends the current provider to `authors` and bumps `updated` on every vault edit — no manual stamping needed. `authors` means "touched the file," not meaningful contribution. Codex only gets this for free once its hook-trust is configured for the llmos plugin; until then, stamp by hand on Codex.
7. Record insight, not activity. GitHub already holds what happened, and the evening digest writes it into each daily note's `## Projects` block. When a day produces a lesson, an open question, or a decision with no ADR yet, write it under `## Thoughts` in `reviews/daily/YYYY-MM-DD.md` — prose, in your own words. Never restate commits, issues, or PRs there. The `## Projects` block is machine-owned — the digest regenerates it wholesale, so never hand-write the day's activity into it.
8. Verify changed notes through Obsidian CLI. Query changed Base views, confirm project backlinks, run `<llmos-plugin-root>/scripts/audit_metadata.py`, check unresolved links, update qmd, retrieve a representative full note, and review Git status.

## Promote recurring patterns

When a workflow or hard-won lesson will recur across projects or providers, create or update a focused sibling skill in this plugin during the same task. Skills live in the agent-toolbox plugins, never in the vault — the vault holds notes. Use the skill creator, keep instructions concise, put deterministic behavior in scripts, and run `quick_validate.py`.

## Git

Commit routine work straight to `main`. Cut a branch only when a diff is worth reading before it lands — a multi-session spec, or a change worth a pull request — and name it `<agent>/<slug>`, with no date. There is no daily branch and no squash-merge closeout; see the vault's ADR 0008.

## Scripts

`audit_metadata.py` does not stamp `authors`/`updated` — the PostToolUse hook owns those. Use `<llmos-plugin-root>/scripts/audit_metadata.py` for a schema audit; it is read-only unless you pass `--fix`.

What the nightly and weekly runs audit, and what neither may ever do, is specified in `references/automation.md`. Read it before acting as either one.

Every canonical spec (`projects/<project>/specs/NNNN-<slug>.md`) carries the minimal `Specifications` category and project ownership. Both are implied by the file's own path, so `--fix` stamps them rather than any agent hand-typing them — run it after `/write-spec` creates a spec, since that command is vault-agnostic and writes only the workflow properties (`status`, `desc`, `blocked`). Legacy supporting notes may remain unclassified until materially edited.
