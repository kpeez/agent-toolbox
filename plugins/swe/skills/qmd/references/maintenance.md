# qmd maintenance and diagnostics

Read this reference when a model-backed query fails, index health is relevant,
or the user explicitly requests setup or maintenance. Diagnostics are
read-only; index changes are not.

## Diagnostics

```bash
qmd status
qmd doctor
```

Run `qmd doctor` first when `query` or `vsearch` fails. If local models or GPU
support are unavailable, return to lexical `qmd search` with stronger terms.

## Explicit maintenance only

These commands change local state and require an explicit setup or maintenance
request:

```bash
qmd collection add /abs/notes --name notes
qmd update [--pull]
qmd embed [-f] [-c <name>]
qmd cleanup
```

Do not infer permission to mutate an index from permission to search it or from
a missing result. Report an unavailable or unhealthy index instead of silently
reconfiguring it.
