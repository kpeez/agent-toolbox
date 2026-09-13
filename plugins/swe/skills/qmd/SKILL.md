---
name: qmd
description: Find and retrieve documents from local Markdown collections indexed by qmd.
user-invocable: false
---

# qmd — query markdown documents

`qmd` searches local Markdown collections such as an Obsidian vault, notes,
docs, wikis, and transcripts. Reach for it when the answer may already live in
the user's own notes. Use the available shell tool to run it.

## Retrieve the source

If the document identity is known, retrieve it directly; a search is not
required. Otherwise, search for candidates, retrieve the relevant source, then
answer from that text. Search snippets are leads, not answers. Do not state
facts, decisions, or quotes from snippets alone.

```bash
qmd get "#abc123"
qmd get qmd://notes/ai-before-headcount.md
qmd multi-get "#abc123,#def432" --format md
```

Results carry a `#docid` and a `qmd://` path. Cite the docid, source path, and
exact line numbers in the answer. Use qmd's line slicing rather than piping
through `sed`, `head`, or `tail`:

```bash
qmd get "#abc123:120:40"
qmd get "#abc123" --from 120 -l 40
```

Use `--full-path` when handing a result to a file reader or editor. Use
`multi-get` when comparing several sources.

## Search and scope

When the source identity is unknown, or when related documents are needed, read
[search modes and collection scope](references/search-modes.md). It covers
lexical, hybrid, and vector selection; structured query fields; and collection
filters. Choose the least expensive mode that can answer the discovery need.

## Maintenance and authority

Search, retrieval, and read-only diagnostics do not mutate the index. Read
[maintenance and diagnostics](references/maintenance.md) when a model-backed
query fails, index health is relevant, or setup and index maintenance are
requested. Never update, embed, add, clean up, or pull an index unless the user
explicitly asked for that maintenance.
