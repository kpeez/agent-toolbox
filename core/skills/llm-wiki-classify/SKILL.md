---
name: llm-wiki-classify
description: Classify one llmOS raw vault file without writing anything. Use as an internal helper for llm-wiki:ingest or for bulk reclassification after schema changes when an agent needs a JSON object with bucket, type, topics, suggested links, source-card recommendation, and reasoning.
---

# llm-wiki:classify

This is an internal helper for `llm-wiki:ingest`. It may also be run directly
after schema changes to re-classify raw files. It is pure: read-only in,
structured JSON out.

> This skill only runs inside the `llmOS` vault at
> `/Users/kyle/Library/Mobile Documents/iCloud~md~obsidian/Documents/llmOS`.
> Abort if run elsewhere.

## Load schema at runtime

Before classifying, re-read these files in this session. Do not hardcode schema
details from this skill; the vault files are canonical.

1. `AGENTS.md` - raw buckets, ownership, entities terminology.
2. `rules/wiki-workflow.md` - classify step in the ingest pipeline.
3. `rules/note-conventions.md` - valid buckets, fine-grained types, source card
   guidance, provenance expectations.
4. `rules/agent-behavior.md` - raw immutability and eager linking.

If any of those files have moved or been renamed, stop and report.

## Input

One vault-relative raw file path, for example:

```text
raw/papers/attention-is-all-you-need.md
```

Reject paths outside `raw/`. Do not move, create, append, rename, delete, or set
properties.

## Read-only workflow

### 1. Read the raw note

```bash
obsidian read path="<raw path>"
obsidian properties path="<raw path>" format=yaml
```

Use the path bucket as the first signal, then verify against content.

### 2. Inspect nearby wiki coverage

Search before inventing links:

```bash
obsidian search query="<topic terms>" path="wiki" limit=20
obsidian files folder="wiki/concepts" ext=md
obsidian files folder="wiki/sources" ext=md
obsidian backlinks path="wiki/concepts/<candidate>.md" counts format=tsv
```

Prefer existing concept names and source cards. Suggested links may include
unresolved `[[wikilinks]]` when the concept is useful but missing.

### 3. Decide source-card recommendation

Use `rules/note-conventions.md` at runtime. In general, papers, long-form
clippings, and deep-research reports recommend source cards; short ideas,
single tweets, and stubs usually do not.

### 4. Return JSON only

Return exactly one JSON object with these fields:

```json
{
  "bucket": "clippings | ideas | tweets | papers | research-reports",
  "type": "<fine-grained type from the runtime rules>",
  "topics": ["<topic1>", "<topic2>"],
  "suggested_links": ["[[Concept A]]", "[[Concept B]]"],
  "source_card_recommended": true,
  "reasoning": "<1-3 sentence explanation>"
}
```

Use a concrete bucket value, not the pipe-delimited placeholder. Keep `topics`
to 3-8 high-signal concepts. Keep `reasoning` short and actionable for ingest.

## What classify does NOT do

- It does not write files.
- It does not set `ingested`.
- It does not create source cards or concept notes.
- It does not fetch URLs or run `defuddle`.
- It does not resolve contradictions.
- It does not decide final wiki edits; ingest uses the returned object as input.

## Reporting back

For direct use, return the JSON object and nothing else. If classification is
impossible, return JSON with the best observed bucket and type, empty arrays
where needed, `source_card_recommended: false`, and a `reasoning` sentence that
states the blocker.
