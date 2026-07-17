---
name: vault-cli
description: Route vault operations to the llmos-vault CLI. Use when reading, listing, moving, linking, or filing notes, working with daily notes, checking vault health, or otherwise needing a deterministic headless verb against the llmOS or xbrain vault instead of hand-typed obsidian-cli calls.
---

# Vault CLI

`llmos-vault` is a cyclopts CLI whose docstrings are the single source of
truth for every verb's parameters, behavior, and output shape. Discovery is
two hops: this table tells you which verb to run, `llmos-vault <cmd> --help`
tells you everything else.

## Verbs

<!-- BEGIN GENERATED VERB TABLE -->
| verb | summary |
| --- | --- |
| `docs` | Regenerate the router skill's command reference from this CLI's tree. |
| `list` | Print every note in the vault with its frontmatter and body as JSON. |
| `neighbors` | Print one note's outgoing links, backlinks, and shared-topic siblings. |
| `read` | Print one note's frontmatter and body as JSON. |
| `subgraph` | Print the transitive neighborhood of a note out to `depth` hops as JSON. |
<!-- END GENERATED VERB TABLE -->

Run `llmos-vault <cmd> --help` for a verb's full parameters, output shape,
and example invocations. The complete per-command docs (the same text
`--help` renders) are also collected in `references/commands.md`.

## Cold-agent walkthrough

Task: "what links to note X". Two hops:

1. Scan the table above for a verb about links -- `neighbors` reads
   "outgoing links, backlinks, and shared-topic siblings".
2. Run it: `llmos-vault neighbors X --vault llmos`.

No prior knowledge of the vault, the library, or Obsidian is required.

## Regenerating this file

This table and `references/commands.md` are generated from the CLI's own
docstrings -- never hand-edit either. After changing a docstring or adding a
verb, run:

```sh
uv run llmos-vault docs
```
