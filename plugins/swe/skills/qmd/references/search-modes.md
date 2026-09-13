# qmd search modes and collection scope

Read this reference when the document identity is unknown, the search needs
semantic recall, or a collection filter is useful. Retrieve the full source
after finding candidates; search output alone is not evidence.

## Choose a mode

| Mode | Command | Use when |
| --- | --- | --- |
| BM25 lexical | `qmd search` | The vocabulary is concrete: titles, names, rare phrases, or code symbols. |
| Hybrid | `qmd query` | The user describes an idea indirectly or wording may not match the source. |
| Vector | `qmd vsearch` | A pure semantic-similarity sweep is useful without keyword anchoring or reranking. |

Start with lexical search for targeted lookups. Use hybrid query for conceptual
recall. Use vector search for a fast semantic sweep. If a model-backed command
fails because local models or a GPU are unavailable, fall back to lexical search
with stronger keywords and consult the diagnostics reference.

## Lexical search

```bash
qmd search "cockpit OKR Goodhart" -n 10
qmd search '"exact phrase in quotes"' -c notes -n 5
qmd search 'sports -baseball' -n 10
```

## Hybrid query

Use the simple form when a natural-language query is sufficient:

```bash
qmd query "how does the metrics-as-instruments idea work"
```

When the goal and domain vocabulary are known, structured fields give more
control over ranking:

```bash
qmd query $'intent: Find the note on metrics as instruments without letting OKRs replace judgment.\nlex: cockpit instruments OKR Goodhart metrics judgment\nvec: data informed not metric driven product judgment\nhyde: A note argues metrics are useful like cockpit instruments, but leaders should stay data-informed rather than metric-driven.'
```

- `intent:` states what to find and what to avoid.
- `lex:` supplies exact terms, aliases, titles, symbols, quoted phrases, or
  negations.
- `vec:` paraphrases the idea in source-like language.
- `hyde:` describes a document or answer that would satisfy the request.

You do not need all four. `intent:` plus one of `lex:` or `vec:` is often
enough. Structured fields cannot be mixed with a standalone expansion query.
Use `--format json --explain` to inspect ranking when needed.

## Vector search

```bash
qmd vsearch "founder stays close to merchant reality through support" -n 10
```

## Scope collections

```bash
qmd collection list
qmd ls
qmd ls xbrain/concepts
qmd search "autonomous agents" -c xbrain -n 10
qmd query "merchant support reality" -c notes -c sources -n 10
```

Omit `-c` to search all collections. Add collection filters when a broad search
drifts into the wrong corpus.

## Common discovery requests

- Known title or term: `qmd search`, then retrieve the top hit.
- Fuzzy idea: use `qmd query` with `intent:` and a `vec:` paraphrase, then
  retrieve the top few hits.
- Cross-source synthesis: retrieve several docids with `qmd multi-get`.
- Exact passage: retrieve with a line slice and cite those lines.
- Vault orientation: use `qmd ls <collection>` or a broad lexical search.
