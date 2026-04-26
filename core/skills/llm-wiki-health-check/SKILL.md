---
name: llm-wiki-health-check
description: Run the llmOS vault /health-check workflow. Use when the user asks for wiki hygiene, orphan or broken-link review, contradiction audit, stale-claim review, frontmatter validation, raw annotation audit, entity deduplication, or index regeneration for the Obsidian LLM wiki.
---

# llm-wiki:health-check

Run this skill for `/health-check`. It is a proposal-and-report workflow for
wiki hygiene. It writes a dated health report and regenerates `index.md`, but
it does not silently apply cleanup decisions.

> This skill only runs inside the `llmOS` vault at
> `/Users/kyle/Library/Mobile Documents/iCloud~md~obsidian/Documents/llmOS`.
> Abort if run elsewhere.

## Load schema at runtime

Before checking anything, re-read these files in this session. Do not hardcode
schema details from this skill; the vault files are canonical.

1. `AGENTS.md` - canonical layout, entities terminology, raw metadata rule.
2. `rules/wiki-workflow.md` - `/health-check` scope and query-first behavior.
3. `rules/note-conventions.md` - note roles, provenance, contradiction format.
4. `rules/agent-behavior.md` - ownership, eager linking, contradiction policy.

If any of those files have moved or been renamed, stop and report.

## Invocation

- `/health-check` - run the full hygiene pass.
- `/health-check scope=<path>` - inspect a narrower subtree when the user asks.

## Health pass

### 1. Inventory the vault

Collect the current wiki, raw, and helper files:

```bash
obsidian files folder="wiki" ext=md
obsidian files folder="raw" ext=md
obsidian files folder="." ext=base
obsidian bases
```

Use this inventory to ground counts and to avoid creating duplicate reports.

### 2. Validate frontmatter and note roles

Read properties through Obsidian:

```bash
obsidian properties path="wiki/concepts/<note>.md" format=yaml
obsidian properties path="wiki/sources/<note>.md" format=yaml
obsidian properties path="wiki/entities/<note>.md" format=yaml
obsidian properties path="raw/<bucket>/<note>.md" format=yaml
```

Compare the observed fields to `rules/note-conventions.md`. Report mismatches
with file paths and proposed fixes. Do not rewrite frontmatter automatically.

### 3. Audit raw annotations

Raw content is user-owned. Check that agent-written raw metadata is limited to
the allowed `ingested` field described by the rules. Use Obsidian properties
and available history evidence:

```bash
obsidian properties path="raw/<bucket>/<note>.md" format=yaml
obsidian history path="raw/<bucket>/<note>.md"
```

If body mutation cannot be proven from available history, say the body audit is
limited instead of guessing.

### 4. Review unresolved links and orphans

List unresolved wikilinks and orphaned notes:

```bash
obsidian unresolved verbose format=tsv
obsidian orphans all
obsidian deadends all
obsidian backlinks path="wiki/concepts/<note>.md" counts format=tsv
obsidian links path="wiki/concepts/<note>.md"
```

For every unresolved wikilink, propose exactly one decision:

- `create stub note` - the target is a reusable concept, source, or artifact.
- `leave as ghost` - the target is useful as a future signal but not worth a
  note yet.

Write the decision proposal to the health report. Do not create stubs.

### 5. Surface contradictions

Search for contradiction sections:

```bash
obsidian search:context query="## Contradictions" path="wiki"
```

Copy concise pointers into the report: target note, claim summary, sources, and
resolution status. Do not resolve contradictions or pick winners.

### 6. Check stale claims and duplicates

Use search, backlinks, aliases, and filenames to find likely stale or duplicate
notes:

```bash
obsidian search query="<claim or topic>" path="wiki" limit=20
obsidian aliases verbose
obsidian backlinks path="wiki/concepts/<note>.md" counts format=tsv
```

Report candidates with reasons and proposed review actions. Do not merge,
rename, delete, or move notes automatically.

### 7. Write the health report

Create one dated report:

```bash
obsidian create path="wiki/entities/health-YYYY-MM-DD.md" content="<markdown>"
```

Use `type: health` frontmatter. Include counts, warnings, unresolved-link
decisions, contradictions, stale-claim candidates, duplicate candidates, raw
audit notes, and any verification limits.

### 8. Regenerate index

As the final step, rebuild root navigation from the current wiki inventory:

```bash
obsidian create path="index.md" content="<markdown>" overwrite
```

The index should stay lightweight: point to the major wiki areas, important
entities, queues, and latest health report.

## What health-check does NOT do

- It does not resolve contradictions.
- It does not create stub notes for unresolved links.
- It does not delete, merge, move, or rename notes.
- It does not rewrite raw bodies.
- It does not ingest raw files or fetch outside sources.
- It does not treat `.base` files as source of truth; they are helper views.

## Reporting back

After the run, report:

1. Path to the health report and whether `index.md` was regenerated.
2. Counts for unresolved links, orphan notes, contradictions, stale candidates,
   duplicate candidates, and raw annotation warnings.
3. The highest-priority decisions awaiting the user.
4. Any checks that were limited by missing history, missing base views, or
   unavailable Obsidian commands.

Keep the chat summary under roughly 20 lines; put detail in the report.
