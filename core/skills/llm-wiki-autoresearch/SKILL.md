---
name: llm-wiki-autoresearch
description: Run the llmOS vault /autoresearch workflow. Use when the user asks for autonomous preserved research, wants the next research-queue item processed, or provides a topic that should gather 5-15 sources, clean them into raw/, ingest them, and draft a synthesis in wiki/entities/.
---

# llm-wiki:autoresearch

Run this skill for `/autoresearch <topic?>`. It is the explicit preservation
path for outside research: fetched sources become raw notes, ingest compiles the
wiki layer, and the final synthesis is a draft for human editing.

> This skill only runs inside the `llmOS` vault at
> `/Users/kyle/Library/Mobile Documents/iCloud~md~obsidian/Documents/llmOS`.
> Abort if run elsewhere.

## Load schema at runtime

Before researching, re-read these files in this session. Do not hardcode schema
details from this skill; the vault files are canonical.

1. `AGENTS.md` - canonical layout, raw ownership, entities terminology.
2. `rules/wiki-workflow.md` - query-first and `/autoresearch` preservation path.
3. `rules/note-conventions.md` - raw buckets, source cards, provenance tags.
4. `rules/agent-behavior.md` - no silent persistence, eager linking, conflicts.

If any of those files have moved or been renamed, stop and report.

## Invocation

- `/autoresearch` - pop the top unchecked item from `research-queue.md`.
- `/autoresearch <topic>` - research the provided topic without reading the
  queue first.

This can run for a while. It is suitable for a daily schedule at 07:00 through
the separate `schedule` skill, but this skill does not register schedules.

## Workflow

### 1. Select the topic

If the user gave a topic, use it. Otherwise read the queue:

```bash
obsidian read path="research-queue.md"
```

Take the first unchecked markdown task. After the draft is written, mark only
that task done:

```bash
obsidian task path="research-queue.md" line=<line-number> done
```

If the queue is empty and no topic was provided, stop and report.

### 2. Query existing coverage

Run `llm-wiki:query` first. Scan `index.md`, search `wiki/`, and read the most
relevant existing notes before going online:

```bash
obsidian read path="index.md"
obsidian search query="<topic terms>" path="wiki" limit=20
```

Use this pass to avoid duplicating known material and to identify questions the
new research should answer.

### 3. Gather sources

Find 5-15 useful sources. Prefer primary sources, canonical docs, papers, and
substantial articles. Keep outside research ephemeral until each source is
intentionally saved into `raw/`.

For standard web pages, clean with `defuddle`:

```bash
defuddle parse <url> --md
```

For markdown URLs, use the markdown directly. For papers, prefer arXiv or the
publisher PDF-to-markdown conversion path already used in the vault.

### 4. Save raw sources

Choose the bucket by source type using the runtime rules:

- `raw/clippings/` for articles, posts, documentation, transcripts, and web
  clippings.
- `raw/papers/` for academic papers and paper conversions.
- `raw/research-reports/` only for long-form agent-authored research reports.

Create raw notes through Obsidian:

```bash
obsidian create path="raw/clippings/<slug>.md" content="<clean markdown>"
obsidian create path="raw/papers/<slug>.md" content="<paper markdown>"
```

Do not save low-quality search results just to hit the source count.

### 5. Ingest new raw files

Run `llm-wiki:ingest` on the newly created raw notes. The ingest skill owns
classification, source cards, concept updates, eager linking, provenance tags,
`ingested` metadata, and `log.md`.

If ingest fails on a source, leave that raw note unstamped and include the
failure in the final report.

### 6. Draft synthesis

Write a draft, not a polished final report:

```bash
obsidian create path="wiki/entities/research-<slug>.md" content="<markdown>"
```

Use `type: research` frontmatter. Include:

- research question
- what the wiki already covered
- new source notes used
- tentative synthesis
- contradictions and uncertainty
- open questions for the user

For a second-opinion pass, delegate synthesis only if the relevant provider
skill is available, such as `codex:rescue` in Codex-specific installs.

## What autoresearch does NOT do

- It does not silently persist outside research outside `/autoresearch`.
- It does not bypass ingest. Raw sources must go through `llm-wiki:ingest`.
- It does not write final polished conclusions. The output is a draft.
- It does not resolve contradictions.
- It does not edit raw note bodies after creating the initial cleaned source.
- It does not register schedules. Use `schedule` separately.

## Reporting back

After the run, report:

1. Topic researched and queue item status.
2. Number of sources found, saved, skipped, and ingested.
3. Paths to raw notes, source cards if created, and the research draft.
4. Any contradictions, weak evidence, or open questions.
5. Any ingest failures or sources left unstamped.

Keep the chat summary compact; put the actual synthesis in
`wiki/entities/research-<slug>.md`.
