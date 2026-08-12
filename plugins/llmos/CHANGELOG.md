# Changelog — llmos plugin

Newest first. Versions are the `version` field shared by
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`.

## 1.0.4 — 2026-08-01

- Make hook commands fish-safe: `${CLAUDE_PLUGIN_ROOT}` becomes
  `"$CLAUDE_PLUGIN_ROOT"`, matching the swe plugin's fix — Codex runs hooks
  through the login shell, where fish rejects `${VAR}` as a syntax error.
- Add the nightly daily-activity digest script: scans monitored projects,
  gates on a content hash, summarizes with one pinned non-interactive OpenCode
  Go call, and writes the digest atomically.
- Update setup tests for the renamed install script and generated
  marketplace catalogs.

## 1.0.3 — 2026-07-17

- Add the `llmos_vault` Python package and the llmos-vault CLI: headless
  read/list verbs, a wikilink graph (neighbors, subgraph), mutation verbs
  (create, move, append, set/remove property) through an obsidian-cli write
  backend, and a vault health report covering orphans, dead-ends, unresolved
  links, schema violations, stale inbox, and qmd gaps.
- Add the `/vault-cli` router skill and generate the command reference docs
  from the CLI tree.
- Register vault hooks: a PreToolUse Bash guard for obsidian-cli targeting
  and vault mv/rm/git-rm, a PostToolUse hook that normalizes frontmatter and
  stamps authors/updated, and a Stop hook that reindexes qmd when dirty.
- Consolidate on one canonical frontmatter serializer; fix list-property
  corruption, mv/rm guard false positives, and bare-basename resolution.
- Add llmOS-profile daily-note helpers and file-inbox filing verbs.
- Skill-quality pass across `/maintain-llmos` and `/setup-llmos`.

## 1.0.2 — 2026-07-17

- Retire the daily-branch model from the plugin.
- Give the Codex hook-trust gate an owner in `/setup-llmos`; stop the
  SessionStart injection asserting a digest that is never built.

## 1.0.1 — 2026-07-16

- Deliver the note contract through the SessionStart injection — the only
  channel a model actually reads — naming the daily note by absolute path.
- Retire the receipt channel and both dead hook symlinks in setup;
  point `/maintain-llmos` at the daily note instead of receipts.
- Cover the metadata-audit seam moved by ADR-0007; drop stale Project Logs
  validation.

## 1.0.0 — 2026-07-16

- Initial release: scaffold the llmOS plugin and migrate core components —
  the `/maintain-llmos` and `/setup-llmos` skills, session hooks
  (`llmos_hook.py`), scripts for metadata audit, daily branches, vault-root
  resolution, daily receipts, and a doctor check, plus their test suite.
