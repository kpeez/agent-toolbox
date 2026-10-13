# Release checks

A broad plugin release runs the packaging checks in `AGENTS.md` and these
offline checks:

- Check that every relative link in changed Markdown resolves.
- Run `claude plugin validate --strict` on the repository root and on each
  changed plugin.
- Load each `agents/*.toml` with Python's `tomllib.load` and each
  `agents/openai.yaml` with `nu -c 'open <file>'`.
- Run `python3 evals/skills/skill_eval.py validate`, and
  `python3 -m unittest discover -s <dir>` for `evals/skills/tests` and
  `plugins/swe/mcp/tests`.
- Load each changed plugin under `plugins/` in Codex with a new temporary
  `HOME` and `CODEX_HOME` set to `$HOME/.codex`:
  `codex plugin marketplace add <checkout>`, then
  `codex plugin add <plugin>@agent-toolbox`, then `codex plugin list`. The
  install is a copy, so add the plugin again after each source edit.
