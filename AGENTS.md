# Repository rules

- Preserve unrelated working-tree changes.
- When a plugin has both `.claude-plugin/plugin.json` and
  `.codex-plugin/plugin.json`, keep their versions identical.
- Bump plugin versions by patch by default, including when adding a skill.
  A minor or major bump requires explicit permission in the request;
  precedent in the git history is not permission.
- Keep every marketplace catalog entry pointed at a plugin folder that exists.
- `plugins/` holds plugins every supported agent can use. `claude-mods/` holds
  Claude Code function-hook mods, which only the Claude catalog lists.
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
  release runs the packaging checks above and these offline checks:
  - Check that every relative link in changed Markdown resolves.
  - Run `claude plugin validate --strict` on the repository root and on each
    changed plugin.
  - Parse each `agents/*.toml` with `python3 -c 'import tomllib'` and each
    `agents/openai.yaml` with `nu -c 'open <file>'`.
  - Run `python3 evals/skills/skill_eval.py validate`, and
    `python3 -m unittest discover -s <dir>` for `evals/skills/tests` and
    `plugins/swe/mcp/tests`.
  - Load each changed plugin in Codex with a new temporary `HOME` and
    `CODEX_HOME` set to `$HOME/.codex`: `codex plugin marketplace add <checkout>`, then
    `codex plugin add <plugin>@agent-toolbox`, then `codex plugin list`. The
    install is a copy, so add the plugin again after each source edit.
- Do not require `pyproject.toml`, a lockfile, or a test suite.
