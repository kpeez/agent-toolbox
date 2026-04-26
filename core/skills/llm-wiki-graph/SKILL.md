---
name: llm-wiki-graph
description: Generate an llmOS wiki topology snapshot as a JSON Canvas artifact. Use when the user runs /graph or asks for a visual map of wiki concepts, sources, entities, backlinks, unresolved links, or the current Obsidian LLM wiki graph.
---

# llm-wiki:graph

Run this skill for `/graph`. It is a thin composition layer over
`json-canvas`: this skill selects scope and gathers vault graph data, while the
`json-canvas` skill owns canvas structure, node IDs, layout, and validation.

> This skill only runs inside the `llmOS` vault at
> `/Users/kyle/Library/Mobile Documents/iCloud~md~obsidian/Documents/llmOS`.
> Abort if run elsewhere.

## Load schema at runtime

Before generating a graph, re-read these files in this session. Do not hardcode
schema details from this skill; the vault files are canonical.

1. `AGENTS.md` - canonical layout and entities terminology.
2. `rules/wiki-workflow.md` - `/graph` role and query-first behavior.
3. `rules/note-conventions.md` - canvas artifact location and note roles.
4. `rules/agent-behavior.md` - eager linking and unresolved-link policy.

If any of those files have moved or been renamed, stop and report.

## Invocation

- `/graph` - generate a current wiki topology snapshot.
- `/graph scope=<path-or-topic>` - graph a narrower subtree or topic if the
  user asks.

## Workflow

### 1. Gather graph inputs

Use Obsidian to inventory notes and links:

```bash
obsidian files folder="wiki" ext=md
obsidian unresolved counts format=tsv
obsidian links path="wiki/concepts/<note>.md"
obsidian backlinks path="wiki/concepts/<note>.md" counts format=tsv
```

For a scoped graph, search first:

```bash
obsidian search query="<topic terms>" path="wiki" limit=30
```

Include concepts, sources, entities, and important unresolved wikilinks. Avoid
adding raw notes unless the user asks for source-level detail.

### 2. Delegate canvas generation

Invoke the `json-canvas` skill with:

- output path: `wiki/entities/graph-YYYY-MM-DD.canvas`
- selected note paths and unresolved targets
- directed link/backlink relationships
- any grouping preference from the user

Let `json-canvas` decide JSON Canvas details: node IDs, edges, groups, layout,
and validation. Do not reimplement those rules here.

### 3. Write the artifact

Create the canvas artifact through Obsidian:

```bash
obsidian create path="wiki/entities/graph-YYYY-MM-DD.canvas" content="<json canvas>"
```

If a graph already exists for the date, either overwrite only with explicit user
approval or create a more specific slug such as
`wiki/entities/graph-YYYY-MM-DD-<topic>.canvas`.

### 4. Validate and inspect

Have `json-canvas` validate the JSON. Then confirm Obsidian can see the file:

```bash
obsidian file path="wiki/entities/graph-YYYY-MM-DD.canvas"
```

Report any intentionally unresolved links as graph signals, not errors.

## What graph does NOT do

- It does not reimplement JSON Canvas generation.
- It does not create, merge, move, or delete wiki notes.
- It does not resolve unresolved links or contradictions.
- It does not ingest raw files or fetch outside research.
- It does not replace `health-check`; it visualizes topology only.

## Reporting back

After the run, report:

1. Canvas path.
2. Number of notes, edges, groups, and unresolved link nodes included.
3. Scope used: full wiki or topic/subtree.
4. Any omitted areas and why.
5. Any validation issue from `json-canvas`.

Keep the chat summary short; the `.canvas` is the durable artifact.
