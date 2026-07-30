# Changelog — lab plugin

Newest first. Versions are the `version` field shared by
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`.

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
