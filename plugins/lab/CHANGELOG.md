# Changelog — lab plugin

Newest first. Versions are the `version` field shared by
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`.

## 1.2.0 — 2026-08-09

- Move bounded `/research` from SWE to Lab as an immediate breaking ownership
  transfer; callers must use `lab:research` after this release.
- Add `/deep-research` for bounded read-only lanes, retained evidence packets,
  deduplicated evidence, citation-audited synthesis, and explicit stop reasons.
- Make `/autoresearch` reproducible around an approved immutable `program.md`,
  frozen evaluator, measured baseline, candidate commits and rollback, and an
  append-only TSV ledger.
- Document Lab's four-skill surface and synchronize the Claude and Codex
  manifests at version 1.2.0.

## 1.1.1 — 2026-07-17

- Skill-quality pass: tighten `/autoresearch` wording and condense the
  data-viz Tufte-perception reference.

## 1.1.0 — 2026-07-16

- Inline documentation guidance in `/autoresearch` instead of pointing at the
  knack plugin's documentation skill; align its references with the knack
  skill-set revamp.
- Manifest resync as the llmos plugin joins both marketplaces.

## 1.0.0 — 2026-06-02

- Initial release: the research half of the old agentspec plugin, carved out
  as lab when the marketplace was renamed agent-toolbox. Ships
  `/autoresearch` (autonomous experiment loop with runs stored under a
  configurable artifacts root, defaulting to a gitignored `.autoresearch/`)
  and `/data-viz` (chart selection, color accessibility, review checklist,
  and Tufte perception references).
