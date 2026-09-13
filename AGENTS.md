# Repository rules

- Preserve unrelated working-tree changes.
- Keep each plugin's `.claude-plugin/plugin.json` and
  `.codex-plugin/plugin.json` versions identical.
- Keep both root marketplace catalogs limited to plugins that exist under
  `plugins/`.
- Keep every skill reference pointed at a resource or script that exists in
  the same plugin.

## Verification

- For plugin packaging changes, parse the affected manifests, catalogs, and hooks
  as direct JSON and verify version, catalog, and resource-reference invariants.
- For changed shell or runtime scripts, run `bash -n`, Python help/usage checks,
  and `python3 -m py_compile` as applicable. Do not run every repository check
  for a docs-only change.
- Run local provider smoke checks against the checked-out catalogs, manifests,
  and hooks without network access when those surfaces change. A broad plugin
  release should run the full offline smoke gate.
- Do not require `pyproject.toml`, a lockfile, or a test suite.
