# Repository rules

- Preserve unrelated working-tree changes.
- When a plugin has more than one of `.claude-plugin/plugin.json`,
  `.codex-plugin/plugin.json`, `.antigravity-plugin/plugin.json`, and the
  root `plugin.json` (Agent Plugins v1, for Hermes Agent), keep their
  versions identical.
- Bump plugin versions by patch by default, including when adding a skill.
  A minor or major bump requires explicit permission in the request;
  precedent in the git history is not permission.
- Keep every marketplace catalog entry pointed at a plugin folder that exists.
  `uv run .github/scripts/plugin_catalogs.py` checks this, and that each
  catalog lists every plugin folder it should.
- A hook that fires on every tool call (`PreToolUse`, `PostToolUse`,
  `PostToolUseFailure`, `PermissionRequest`) runs TypeScript through
  `scripts/run-ts`, or cats a `.md` file. Startup cost adds up on these
  hooks. Bun starts in about 12 ms. `uv run --script` starts in about 33 ms
  (measured on an M-series Mac).
- `scripts/run-ts` runs the file with bun when bun is installed. Otherwise it
  runs the file with Node 22.18 or later. Each plugin whose hooks use run-ts
  ships its own copy. The copies stay byte-identical.
- A hook on any other event may also run a `uv run --script` Python file.
  Agent scripts off the per-call path default to Python. Analysis, plotting,
  and experiment tools stay Python. TypeScript stays where the code is synced
  from upstream pstack (statechart, recall transcripts) or already exists.
- Use erasable TypeScript syntax only (`erasableSyntaxOnly`). No enums,
  namespaces, or parameter properties. Use `import type` for type-only
  imports. Node 22.18 and later then runs the same `.ts` files with no build
  step.
- Use only `node:` APIs, never `Bun.*` or `import.meta.dir`. The same file
  must run on bun and on Node unchanged.
- Never use `import.meta.main`. Node 23.6 to 24.1 strips types but leaves it
  undefined, so `main()` never runs. Compare `process.argv[1]` with the
  module path, as `isMain` in `plugins/rex-agents/scripts/is_main.ts` does.
- Start each Python script with `#!/usr/bin/env -S uv run --script` and a
  PEP 723 header that sets `requires-python = ">=3.11"` and lists its
  dependencies. Never use `python3`. The header keeps `uv run` from syncing the
  project that a hook runs in.
- `.github/scripts/hook_runtime.py` enforces these runtimes. It fails CI
  when a plugin hook runs anything else.
- `plugins/` holds plugins every supported agent can use. `claude-mods/` holds
  Claude Code function-hook mods, which only the Claude catalog lists.
- Keep every skill reference pointed at a resource or script that exists in
  the same plugin. A plugin never names another plugin's skill, agent, or
  playbook, not even "when it is installed". Write the rule inline. Copy a
  skill into each plugin, as with `go-deeper`, only when every plugin needs
  it, it is not specific to one domain, and a few inline lines cannot replace
  it.
  `uv run .github/scripts/plugin_isolation.py` catches `<plugin>:<name>`
  references; a bare name such as `interview-user` in lab is yours to catch.
- `go-deeper` lives in `plugins/swe`, `plugins/lab`, and `plugins/uni` so each
  plugin installs alone. Edit all three copies together; the `checks`
  workflow fails when they differ.
- Put repo-local skills in `.agents/skills/`. `.claude/skills` is a committed
  link to that folder, so Claude Code and Codex read one copy.
- To pull upstream pstack changes into swe, use the repo-local
  `sync-pstack-upstream` skill.
- Before you add a rule for a repeated agent mistake, read
  [docs/agent-rule-enforcers.md](docs/agent-rule-enforcers.md) and follow the
  `correct` skill in `plugins/swe`.

## Verification

- For plugin packaging changes, parse the affected manifests, catalogs, and hooks
  as direct JSON and verify version, catalog, and resource-reference invariants.
- For changed shell or runtime scripts, run `bash -n`, Python help/usage checks,
  and `uv run -m py_compile` as applicable. Do not run every repository check
  for a docs-only change.
- Run local provider smoke checks against the checked-out catalogs, manifests,
  and hooks without network access when those surfaces change. A broad plugin
  release also runs the link, plugin-validation, agent-config, eval, unit-test,
  and Codex-load checks in [docs/release-checks.md](docs/release-checks.md).
- Do not require `pyproject.toml`, a lockfile, or a test suite.
- After a change to `plugins/uni/skills/tech-tree/scripts/tech_tree.py` or
  the rules in its `SKILL.md` or `GRAPH-FORMAT.md`, run
  `uv run .agents/skills/verify-tech-tree/scripts/check.py`. It checks the
  gate and scheduling rules in every reachable state. The
  `verify-tech-tree` skill says what it covers.
- After you change a path that a skill in `.agents/skills/verify-*` lists in its
  `paths`, run that skill. For `plugins/swe` hooks, run
  `uv run .agents/skills/verify-swe-hooks/scripts/check.py`.
