---
status: active
authors:
  - codex
  - gemini
created: 2026-07-15
updated: 2026-07-15
categories:
  - "[[agents/Agent infrastructure]]"
topics:
  - "[[Knowledge management]]"
  - "[[Obsidian]]"
---


# llmOS note schema

## Property example

```yaml
---
status: active
authors:
  - codex
created: 2026-07-15
updated: 2026-07-15
categories:
  - "[[Knowledge]]"
---
```

- `status`: specs advance `draft` → `active` → `review` → `done`, plus `archived`; ADRs use `proposed`, `accepted`, or `superseded`.
- `authors`: append-only list using `claude`, `codex`, `gemini`, or `human`.
- `created`: original creation date; never rewrite it.
- `updated`: date of the latest meaningful edit.
- `categories`: one or more linked identities such as `[[Knowledge]]`, normally one.
- `topics`: zero or more linked concepts describing what the note is about.
- `project`: path-qualified link such as `[[projects/llmos/llmos|llmOS]]`; remains only where it establishes actual project ownership. Omit the self-link on a canonical project note/landing page.

Omit empty properties. Use `categories`, `topics`, and `project` only when the note actually needs them. Do not seed empty arrays, generic boilerplate, or a copied taxonomy.
Keep operational properties such as status/authors/dates only when useful; omit empty tags/project lists.

All graph properties are YAML lists of wikilinks, even when one value is normal. Link named concepts, decisions, tools, sources, and projects whenever a future reader may remember them by name. Useful unresolved links are allowed; recurring variants are canonicalized during weekly review.

Every canonical spec (`projects/<project>/docs/specs/NNNN-<slug>.md`) carries the minimal `Specifications` category and project ownership; legacy supporting notes may remain unclassified until materially edited.

## Spec property ownership

A spec's frontmatter has two owners, and neither writes the other's fields.

**`/write-spec` (the knack plugin) owns the workflow properties.** They are vault-agnostic and ship to every knack user:

- `status`: the spec's own lifecycle, set to `draft` at creation. `/to-issues` advances it to `active`, `/ship-pr` to `review`, and a completion receipt to `done`. This is not a task ledger — the tracker still owns every task.
- `desc`: one or two sentences on what the spec does, so a Base view or a directory listing is triageable without opening each file.
- `blocked` / `blocked_reason`: orthogonal to `status`, because a spec is blocked *at* a phase. Omit both unless actually blocked.

**llmOS owns the graph properties**: `categories`, `project`, and `authors`. All three are derivable from the file's own path, so `audit_metadata.py --fix` stamps them rather than any agent hand-typing them. Never fabricate historical authors or dates. Backfill the full schema when a legacy file is materially edited; use `ingested` when the original creation date is not defensible.

## Directory map

- `inbox/`: unprocessed captures.
- `knowledge/`: shared cross-project knowledge and reflections.
- `projects/<project>/docs/`: project design and references.
- `projects/<project>/docs/specs/`: project specifications.
- `projects/<project>/docs/adrs/`: project architecture decisions.
- `agents/<provider>/`: provider-native memory and routing.
- `agents/skills/`: shared operational skills, scripts, tools, binaries, and hooks.
- `reviews/daily/`: cross-project created-note aggregation, managed project summaries, and genuinely projectless receipts.
- `projects/<project>/logs/`: project-owned per-date receipts named `YYYY-MM-DD-<project>.md`.
- `reviews/weekly/`: cross-project weekly synthesis.
- `sources/`: immutable source material.
- `archive/`: inactive material.
- `categories/`: category hubs.
- `templates/bases/`: canonical Obsidian Base definitions.

Folder structure is mapped in the landing note `llmOS.md`; Bases provide dynamic inventories. Internal vault links use `[[wikilinks]]`; external links use Markdown links.

## Daily log contract

Project logs have exactly one path-qualified `project` owner, `categories: ["[[Project Logs]]"]`, append-only `authors`, `created`, `updated`, a descriptive project/date title, `Daily review: [[YYYY-MM-DD]]`, and a `## Receipts` section. Receipt markers are `<!-- llmos-receipt:<agent>:<turn-id>:<project> -->`; the same marker is a no-op on rerun. The top-level daily review has no project property, embeds `Daily Reviews.base#Created on day`, and reserves `## Cross-project receipts` for material work with no project owner.
