# Repository rules

- Preserve unrelated working-tree changes.
- No plugin manifest or catalog entry sets `version`;
  `uv run .github/scripts/manifest_versions.py` says why.
- Keep every marketplace catalog entry pointed at a plugin folder that exists.
  `uv run .github/scripts/plugin_catalogs.py` checks this, and that each
  catalog lists every plugin folder it should.
- A hook that fires on every tool call (`PreToolUse`, `PostToolUse`,
  `PostToolUseFailure`, `PermissionRequest`) must start no runtime on a call
  it does not act on. Gate it in front of the runtime: a
  `[ -n "$VAR" ] || exit 0; ` guard in `hooks.json`, or a POSIX sh gate
  (`sh "$CLAUDE_PLUGIN_ROOT"/<path>.sh`) that reads stdin with builtins and
  sources `scripts/run-ts` only on a match. A test must run the hook through
  its gate, so a gate that skips a call the hook acts on fails. Do not gate
  with the hook `if` field: `Bash(*gh*)` does not start the hook for
  `bash <<'EOF'` with `gh pr create` inside.
- Behind the gate, a per-call hook runs TypeScript through `scripts/run-ts`,
  or cats a `.md` file. Medians from 100 shuffled samples on an M1 Pro: the
  PR-body hook on a no-op Bash call takes 29 ms ungated on bun, 92 ms on
  Node, and 15 ms gated. The Rex mirror hook outside Rex takes 28 ms ungated
  and 9 ms behind its guard. `sh -c :` alone takes 9 ms. A bare bun start
  takes 11 ms, `uv run --script` 32 ms.
- No compiled or bundled hooks. Plugins install from a Git checkout with no
  build step, and a bundle loads no faster than the source under bun.
- `scripts/run-ts` runs the file with bun when bun is installed. Otherwise it
  runs the file with Node 22.18 or later. With neither, it exits 1, which
  Claude Code shows as a non-blocking hook error that names the fix. Each
  plugin whose hooks use run-ts ships its own copy. The copies stay
  byte-identical.
- A hook on any other event may also run a PEP 723 `uv run --script` Python
  file.
  Agent scripts off the per-call path default to Python. Analysis, plotting,
  and experiment tools stay Python. TypeScript stays where the code is synced
  from upstream pstack (statechart, recall transcripts) or already exists.
- Use erasable TypeScript syntax only (`erasableSyntaxOnly`). No enums,
  namespaces, or parameter properties. Use `import type` for type-only
  imports. Node 22.18 and later then runs the same `.ts` files with no build
  step.
- Use only `node:` APIs, never `Bun.*` or `import.meta.dir`. The same file
  must run on bun and on Node unchanged.
- Start each Python script with `#!/usr/bin/env -S uv run --script` and a
  PEP 723 header that sets `requires-python = ">=3.11"` and lists its
  dependencies. Never use `python3`. The header keeps `uv run` from syncing the
  project that a hook runs in.
- `.github/scripts/hook_runtime.py` enforces these runtimes. It fails CI
  when a plugin hook runs anything else.
- `plugins/` holds plugins every supported agent can use. `claude-mods/` holds
  Claude Code function-hook mods, which only the Claude catalog lists.
- Keep every skill reference inside its own plugin. A plugin never names another plugin's skill, agent, or
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
  as direct JSON.
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
- After a change to the eval-batch budget in `evals/skills/run_eval.py`
  (`Batch`, `spend`, `finished`, `prepare`, `launch`, or `execute`), run
  `uv run .agents/skills/verify-eval-budget/scripts/check.py`. It
  model-checks the budget cap and resume with TLC and replays each model
  step on the real code.
