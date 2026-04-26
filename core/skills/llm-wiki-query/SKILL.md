---
name: llm-wiki-query
description: Run the always-on query-first loop for the llmOS Obsidian vault. Use on every substantive prompt in that vault, or explicitly when an agent needs to scan the wiki, read relevant notes, answer with wikilink citations, and optionally file a durable query answer into wiki/entities/queries/.
---

# llm-wiki:query

This is the always-on default behavior for the llmOS vault, not a slash command.
Run it implicitly before answering any substantive prompt in the vault. The
skill file exists so the loop can also be invoked explicitly when another skill
needs query context.

> This skill only runs inside the `llmOS` vault at
> `/Users/kyle/Library/Mobile Documents/iCloud~md~obsidian/Documents/llmOS`.
> Abort if run elsewhere.

## Load schema at runtime

Before answering, re-read these files in this session. Do not hardcode schema
details from this skill; the vault files are canonical.

1. `AGENTS.md` - canonical layout, entities terminology, raw ownership.
2. `rules/wiki-workflow.md` - Default Step 0 and durable filing policy.
3. `rules/note-conventions.md` - note roles, frontmatter, provenance tags.
4. `rules/agent-behavior.md` - query-first, eager linking, contradiction rules.

If any of those files have moved or been renamed, stop and report.

## Query loop

### 1. Scan navigation

Read the root index first:

```bash
obsidian read path="index.md"
```

Use it to identify likely concepts, source cards, entities, and query archive
notes related to the user's prompt.

### 2. Locate nearby notes

Search the maintained wiki layer before reading raw material:

```bash
obsidian search query="<topic terms>" path="wiki" limit=20
obsidian base:query path="wiki.base" view="<relevant view>" format=json
```

If the base view does not exist or fails, use `obsidian files folder=wiki
ext=md` plus targeted `obsidian search` calls. Prefer `wiki/concepts/` and
`wiki/sources/` for grounding; use `wiki/entities/` when the prompt asks about
a prior synthesis, health report, graph, or query archive.

### 3. Read TLDRs, then full notes

Read matching frontmatter, first paragraphs, or top summary sections first.
Then read the 1-5 most relevant notes in full:

```bash
obsidian read path="wiki/concepts/<note>.md"
obsidian read path="wiki/sources/<source>.md"
obsidian read path="wiki/entities/<artifact>.md"
```

Only read raw notes when the wiki layer is missing necessary detail or the user
specifically asks for source evidence.

### 4. Synthesize with citations

Answer from the notes you actually read. Cite claims with `[[wikilinks]]` to
the relevant concept, source, or artifact notes.

Hard rules:

- Never fabricate citations.
- Never say "I could not find anything" unless you actually ran the loop.
- Surface contradictions and uncertainty instead of smoothing them over.
- If you rely on raw material directly, make that provenance explicit.

### 5. File durable answers

If the question and answer are likely to be useful later, file them as a query
artifact:

```bash
obsidian create path="wiki/entities/queries/YYYY-MM-DD-<slug>.md" \
  content="<markdown>"
```

Use `type: query` frontmatter and link the source notes used. Transient chat
answers, quick status checks, and one-off operational replies do not get filed.

## What query does NOT do

- It is not a slash command and should not be presented as `/query`.
- It does not ingest new raw files. Use `llm-wiki:ingest`.
- It does not fetch outside sources. Use `llm-wiki:autoresearch` when research
  should be preserved.
- It does not resolve contradictions. List them and point to the relevant notes.
- It does not create broad new structure. File only durable query artifacts.

## Reporting back

When the query loop materially affects the answer, report:

1. Which wiki notes grounded the answer.
2. Whether raw material was needed.
3. Whether a durable query artifact was filed, with its path.
4. Any contradictions, stale claims, or missing notes discovered.

Keep routine reports brief; the citations in the answer usually carry the load.
