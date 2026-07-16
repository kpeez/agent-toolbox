---
name: qmd
description: Search local markdown knowledge bases — Obsidian vaults, notes, docs, wikis, transcripts — with the qmd CLI. Use when the user asks to find notes, retrieve documents, answer from indexed markdown, hunt for semantically related files, or inspect what a vault contains.
user-invocable: false
---

# qmd — query markdown documents

`qmd` searches local markdown collections (the user's Obsidian vault and other
indexed folders) from the shell. Reach for it before web search when the answer
may already live in the user's own notes.

The workflow is always:

1. **Search** for candidate documents (pick a mode — see below).
2. **Retrieve** the full source with `qmd get` / `qmd multi-get`.
3. **Answer** from retrieved text, citing the `#docid`, path, and line numbers.

Snippets are leads, not answers. Do not state facts, decisions, or quotes from
search snippets alone — fetch the document first.

Run everything via `Bash`. Searching and retrieving are read-only and safe to run
without gating; only index mutation (`update`, `embed`, `collection add`) changes
state — never do that unless the user asked for setup or maintenance.

## Pick the right mode

Three search modes, in order of how often you'll want them:

| Mode | Command | Uses LLM/embeddings? | Reach for it when |
|------|---------|----------------------|-------------------|
| **BM25 lexical** | `qmd search` | No | You know the words — titles, names, rare phrases, code symbols. Fast, no model. **The default for targeted lookups.** |
| **Hybrid query** | `qmd query` | Yes (expansion + rerank) | You're hunting for semantically related files, the user describes an idea indirectly, or wording won't match the source. Richer, slower. |
| **Vector** | `qmd vsearch` | Embeddings only | You want pure semantic similarity with no keyword anchoring or rerank overhead — quick "what's near this idea" sweeps. |

Rule of thumb: **`search` first when you have concrete terms; reach for `query`
when you need conceptual recall or related-file discovery.** If `query` or
`vsearch` fails because local models/GPU aren't available, fall back to `search`
with stronger keywords.

### `qmd search` — BM25, easy and targeted

```bash
qmd search "cockpit OKR Goodhart" -n 10
qmd search '"exact phrase in quotes"' -c notes -n 5
qmd search 'sports -baseball' -n 10          # negation: exclude a term
```

Best for exact words, page titles, named entities, and code symbols. No model
runs, so it's the fastest mode and often the best when you already know the
vocabulary.

### `qmd query` — hybrid, rich, semantic hunting

The recommended mode for conceptual recall and finding related files. Two forms:

```bash
# Simple: one line, qmd expands it for you
qmd query "how does the metrics-as-instruments idea work"

# Structured: you author the fields — preferred when you know the domain
qmd query $'intent: Find the note on metrics as instruments without letting OKRs replace judgment.\nlex: cockpit instruments OKR Goodhart metrics judgment\nvec: data informed not metric driven product judgment\nhyde: A note argues metrics are useful like cockpit instruments, but leaders should stay data-informed rather than metric-driven.'
```

When you know the user's actual goal and the domain vocabulary, **write the
structured fields yourself** rather than leaning on the expansion model — you're
the better query expander:

- `intent:` — what you're trying to find **and what to avoid**. Steers ranking
  away from nearby-but-wrong concepts. Supply it whenever wording is ambiguous.
- `lex:` — exact terms, aliases, titles, code symbols, rare words (your keyword
  expansion). Supports quoted phrases and `-negation`.
- `vec:` — the idea paraphrased in natural, source-like wording.
- `hyde:` — a description of the document/answer that would satisfy the request.

You don't need all four. A good structured query is usually `intent:` plus one
of `lex:`/`vec:`. Standalone expand queries can't mix with typed lines.

```bash
qmd query --format json --explain $'intent: ...\nlex: ...\nvec: ...'   # inspect ranking
```

### `qmd vsearch` — pure vector similarity

```bash
qmd vsearch "founder stays close to merchant reality through support" -n 10
```

Embeddings only — no BM25 anchor, no rerank. Use for fast "what notes are near
this idea" sweeps. Prefer `query` when you want the rerank to sharpen results.

## Retrieve sources

Results carry `#docid`s and `qmd://...` paths. Fetch the full text before
answering:

```bash
qmd get "#abc123"
qmd get qmd://notes/ai-before-headcount.md
qmd multi-get "#abc123,#def432" --format md
qmd multi-get 'notes/{customer-proximity.md,data-informed.md}' --format md
qmd multi-get 'sources/podcast-2025-*.md' -l 80
```

Use `multi-get` when comparing several hits or gathering context across pages.

### Output is line-numbered and carries the docid — cite both

`get`/`multi-get` print the `#docid` and `qmd://` path, then line-numbered
content:

```text
qmd://notes/note.md  #abc123
---

1: # Metrics as instruments
2:
3: Treat dashboards like cockpit instruments...
```

Cite the docid and exact line numbers in your answer, and use the numbers to ask
for the next slice. Add `--no-line-numbers` only when reproducing content
verbatim (e.g. copying a code block).

Add `--full-path` when you need an on-disk path to hand to `Read`, `Edit`, or an
editor — it replaces the `qmd://` header with the real filesystem path
(`./`-prefixed inside `$PWD`, absolute otherwise) and drops the docid. Works on
`search`/`query`/`vsearch` results too. Otherwise keep the default `qmd://` URIs.

### Read line ranges with `:from:count` — never pipe through `sed`/`head`/`tail`

`qmd get` slices files itself. Piping defeats docid resolution, virtual paths,
line numbering, and the header.

```bash
qmd get "#abc123:120:40"               # 40 lines starting at line 120
qmd get qmd://notes/note.md:200:60     # lines 200–259
qmd get "#abc123:120"                  # from line 120 to end of file
qmd get "#abc123" --from 120 -l 40     # equivalent, using flags
```

- `<path>:<from>:<count>` — start at `<from>`, read `<count>` lines. Best for
  reading around a search hit.
- `<path>:<from>` — start at `<from>`, read to end.
- `--from <line>` / `-l <lines>` — flag equivalents (override the suffix).

Search hits include a `:line` anchor — feed it straight in:
`qmd get path:line:<n>` reads a window around the match.

Wrong: `qmd get "#abc123" | sed -n '120,160p'`
Right: `qmd get "#abc123:120:40"`

## Scope to collections

```bash
qmd collection list                                  # what's indexed
qmd ls                                               # browse indexed files
qmd ls xbrain/concepts                               # browse a subtree
qmd search "autonomous agents" -c xbrain -n 10       # restrict to one collection
qmd query "merchant support reality" -c notes -c sources -n 10
```

Omit `-c` to search everything. Add a collection filter when a broad search
drifts into the wrong corpus.

## Use cases at a glance

- **"Find my note about X"** (you know the title/term) → `qmd search "X" -n 5`,
  then `qmd get` the top hit.
- **"What have I written related to <fuzzy idea>?"** → `qmd query` with an
  `intent:` and a `vec:` paraphrase; fetch the top 2–3 with `multi-get`.
- **Gather context across several notes for a synthesis** → `qmd query` to find
  hits, then `qmd multi-get "#id1,#id2,#id3" --format md`.
- **Pull an exact quote or passage** → `qmd get "#docid:from:count"`, cite the
  line numbers.
- **Hand a note to `Read`/`Edit`** → `qmd get "#docid" --full-path` to get the
  on-disk path.
- **"What's in my vault about Y?" / orientation** → `qmd ls <collection>` to
  browse, or a broad `qmd search` to scan.

## Status and maintenance

Read-only diagnostics are always safe:

```bash
qmd status        # index + collection health
qmd doctor        # config, model cache, GPU/device, vector fingerprints
```

Run `qmd doctor` first whenever a model-backed command (`query`/`vsearch`) fails.

**Only mutate indexes when the user explicitly asks for setup or maintenance** —
these change local state and can be slow:

```bash
qmd collection add ~/notes --name notes   # index a new folder
qmd update [--pull]                        # re-index (optionally git pull first)
qmd embed [-f] [-c <name>]                 # (re)generate vector embeddings
qmd cleanup                                # clear caches, vacuum DB
```

## Pitfalls

- **Don't stop at snippets.** Fetch documents with `get`/`multi-get` before
  making claims.
- **Don't slice with `sed`/`head`/`tail`.** Use `path:from:count` or
  `--from`/`-l`; output is already line-numbered.
- **Don't overuse semantic search.** If you know exact titles or terms, `search`
  (BM25) is faster and often better than `query`/`vsearch`.
- **Don't lean blindly on query expansion.** When you know the domain, author
  `intent:`/`lex:`/`vec:`/`hyde:` yourself — you expand, the model ranks.
- **Don't mutate indexes casually.** `collection add`, `update`, and `embed`
  change state and can be expensive — gate them on an explicit request.
- **Model-backed commands are environment-sensitive.** If `query`/`vsearch` fail
  (no local model/GPU), fall back to `search` with stronger lexical terms.
