# qmd maintenance and diagnostics

Read this reference when a model-backed query fails, index health is relevant,
or the user explicitly requests setup or maintenance. Diagnostic commands may
need write access to open the index; they are not a safe fallback when the
filesystem must stay strictly read-only.

## Diagnostics

```bash
qmd status
qmd doctor
```

When `query` or `vsearch` fails, use `qmd doctor` if index access permits it.
If diagnostics cannot open the index, try available lexical `qmd search` with
stronger terms or report the index-access limitation. Do not repair the index
as a side effect of retrieval.

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
