---
name: llm-wiki-ingest
description: Process unprocessed raw notes in the llmOS vault through the 8-step compile pipeline that loads the raw queue, sorts and resolves sources, classifies, compiles wiki entries, eager-links, provenance-checks, stamps ingested, and logs. Use when the user runs /ingest, drops new material into raw/, or asks to process or compile the queue.
---

# llm-wiki:ingest

The compile step of the Karpathy LLM-wiki pattern. Raw notes in, wiki notes
out. Query time is cheap because compile time does the work.

> This skill only runs inside the `llmOS` vault at
> `/Users/kyle/Library/Mobile Documents/iCloud~md~obsidian/Documents/llmOS`.
> Abort if run elsewhere.

## Load schema at runtime

Before processing anything, re-read these files in this session. Do not
hardcode schema details from this skill; the vault files are canonical.

1. `AGENTS.md` - canonical layout, entities terminology, raw metadata
   exception.
2. `rules/note-conventions.md` - frontmatter fields, provenance tags,
   contradictions template, source card schema.
3. `rules/wiki-workflow.md` - the 8-step pipeline this skill implements.
4. `rules/agent-behavior.md` - ownership, eager linking, contradictions policy.

If any of those files have moved or been renamed, stop and report.

## Invocation

- `/ingest` - process every unprocessed raw note.
- `/ingest path=<relative/path>` - process one specific file, even if already
  stamped.
- `/ingest --force` - re-process everything, ignoring existing `ingested`
  stamps. Rare; usually only after a schema change.

## Step 0 - Load the queue

Read `raw-queue.base` to get the unprocessed list. The base filters for
`file.inFolder("raw") and !ingested`.

```bash
obsidian base:query path="raw-queue.base" view="Unprocessed" format=paths
```

If the `!ingested` filter syntax errors, fall back to:

```bash
obsidian base:query path="raw-queue.base" view="Unprocessed" format=json
```

Filter client-side for missing `ingested` and report the base syntax issue so
it can be fixed.

Result: an ordered list of raw paths to process. If empty, announce "queue
empty" and stop.

## Per-file pipeline

Process files one at a time. A failure on one file must not corrupt state for
others. If a step fails mid-file, leave the raw note unstamped so the next run
retries it, and log the failure.

### Step 1 - Sort and resolve

Verify the file's bucket matches its content:

- `raw/clippings/` - web clippings, articles, video transcripts, YouTube notes.
- `raw/ideas/` - freeform notes, voice memos, stubs.
- `raw/tweets/` - X/Bluesky archives.
- `raw/papers/` - academic papers, arXiv notes, journal articles, PDF
  conversions.
- `raw/research-reports/` - long-form agent-authored deep research.

If the file's bucket is clearly wrong, do not move it yourself. Propose the
move in the run report and ask. Raw is user-owned for content.

If the raw body is a URL or starts with `Clipped from <url>`, resolve it via
`defuddle parse <url> --md` and write the clean markdown into the same file
body. This is the narrow exception to raw-body immutability: only do it when the
file is a URL stub with no other content. Note the resolution in `log.md`.

Extract linked media into the same folder under a `media/` sibling only when the
source needs it.

### Step 2 - Classify

For each raw file, determine:

- `type` - the fine-grained class inside its bucket, such as `paper`, `video`,
  `article`, `transcript`, `post`, `idea`, or `deep-research`.
- `topics` - 3-8 concepts the source touches.
- `suggested_links` - candidate `[[wikilinks]]` to existing or useful future
  notes.

Use Obsidian discovery before inventing new links:

```bash
obsidian search query="<topic terms>" path="wiki" limit=20
obsidian backlinks path="wiki/concepts/<candidate>.md" counts format=tsv
```

Invoke `llm-wiki-classify` when available. It is the pure helper for this step.

### Step 3 - Compile wiki entries

For each topic, create or update the minimum set of wiki notes:

- Concept notes in `wiki/concepts/`.
- Source cards in `wiki/sources/` for papers, long-form clippings, and
  deep-research reports.
- Entity syntheses in `wiki/entities/` only if explicitly requested or the
  source is a major synthesis target. Usually this belongs to
  `llm-wiki-autoresearch`, not ingest.

Every wiki edit goes through Obsidian CLI commands so backlinks and metadata
stay consistent:

```bash
obsidian create path="wiki/concepts/<topic>.md" content="<markdown>"
obsidian append path="wiki/concepts/<topic>.md" content="<markdown>"
obsidian property:set path="<raw path>" name="ingested" value="<YYYY-MM-DD>"
```

Never use plain `mv`, `rm`, `cat >`, or `echo >` for vault operations that
should update Obsidian's app model. Use `obsidian move`, `obsidian delete`,
`obsidian create`, and `obsidian append`.

### Step 4 - Eager cross-link

For every concept, entity, or source the new or updated note mentions in prose,
wrap it in `[[wikilinks]]`, even if the target note does not yet exist.
Unresolved links are useful signals for `llm-wiki-health-check`.

Rules:

- Prefer bare filenames, such as `[[RLHF]]`, over path-prefixed forms.
- Link on first mention in each note, not every mention.
- Link meaningful concepts, entities, and sources, not filler words.

### Step 5 - Provenance check

Every new wiki claim that depends on a source must carry one of:

- `*(extracted)*` - stated directly in the source.
- `*(inferred)*` - follows from the source but is not stated.
- `*(ambiguous)*` - source is unclear or contested.

No citation means no claim. If you cannot point to a source, do not assert the
fact.

If a new claim contradicts an existing claim in the target note, do not pick a
winner. Append or create a `## Contradictions` section using the template in
`rules/note-conventions.md`. Surface both sides and mark `Resolution: open`.

### Step 6 - Stamp ingested

Write `ingested: <today ISO date>` into the raw file's frontmatter. This is the
only metadata field agents may write on raw notes.

```bash
obsidian property:set path="<raw path>" name="ingested" value="<YYYY-MM-DD>"
```

Use `property:set`, not direct file edits. This preserves YAML structure and
touches only the one field.

### Step 7 - Log

Append one line to `log.md` for each processed file:

```bash
obsidian append path="log.md" content="## [YYYY-MM-DD] ingest | <raw-basename>\n\n<summary>"
```

Batch the day's ingests under a single date heading when running on multiple
files.

## Idempotency

- Files already stamped `ingested` are skipped unless `--force` is passed.
- Re-running `/ingest` on the same queue immediately after a successful run is
  a no-op.
- Step 6 is the commit point. If the pipeline fails before step 6, the file
  stays in the queue and retries cleanly.

## What ingest does NOT do

- It does not regenerate `index.md`. That is `llm-wiki-health-check`'s job.
- It does not resolve contradictions. List them, do not decide.
- It does not move raw files between buckets. Propose, do not move.
- It does not delete raw files.
- It does not run deep research. That is `llm-wiki-autoresearch`'s job.
- It does not create broad new structure beyond the minimum wiki notes needed.

## Reporting back

After the run, report:

1. Number of files processed and skipped as already ingested.
2. Wiki notes created vs. updated, with counts per role.
3. Source cards created or updated.
4. Any contradictions surfaced.
5. Any bucket mismatches that need the user's attention.
6. Any failures: which file, which step, and what to fix.

Keep the report under roughly 20 lines unless something unusual happened.
