# Repository rules

- Preserve unrelated working-tree changes.
- Keep each plugin's `.claude-plugin/plugin.json` and
  `.codex-plugin/plugin.json` versions identical.
- Bump plugin versions by patch by default, including when adding a skill.
  A minor or major bump requires explicit permission in the request;
  precedent in the git history is not permission.
- Keep both root marketplace catalogs limited to plugins that exist under
  `plugins/`.
- Keep every skill reference pointed at a resource or script that exists in
  the same plugin.

## Verification

- Parse manifests, catalogs, and hooks as direct JSON.
- Run `bash -n` on every surviving shell script.
- Run Python `--help` or usage checks and `python3 -m py_compile` on runtime
  scripts.
- Run local provider smoke checks against the checked-out catalogs, manifests,
  and hooks without network access.
- Do not require `pyproject.toml`, a lockfile, or a test suite.
