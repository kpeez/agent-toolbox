# Release checks

A broad plugin release runs the packaging checks in `AGENTS.md` and these
offline checks:

- Check that every relative link in changed Markdown resolves.
- Run `claude plugin validate` on the repository root and on each changed
  plugin. Do not add `--strict`: the manifests have no `version` on purpose,
  and strict mode fails on that warning.
- Run `hermes plugins validate plugins/<plugin>` on each changed plugin when
  Hermes Agent is installed.
- Load each `agents/*.toml` with Python's `tomllib.load` and each
  `agents/openai.yaml` with `nu -c 'open <file>'`.
- Run `uv run evals/skills/skill_eval.py validate`,
  `uv run evals/skills/facets.py check`, and
  `uv run -m unittest discover -s evals/skills/tests`.
- Run `uv run .github/scripts/hook_runtime.py` to check that every plugin
  hook follows the runtime table for its event: `scripts/run-ts` TypeScript,
  `cat` text, or uv Python off the per-call path.
- Load each changed plugin under `plugins/` in Codex with a new temporary
  `HOME` and `CODEX_HOME` set to `$HOME/.codex`:
  `codex plugin marketplace add <checkout>`, then
  `codex plugin add <plugin>@agent-toolbox`, then `codex plugin list`. The
  install is a copy, so add the plugin again after each source edit.
