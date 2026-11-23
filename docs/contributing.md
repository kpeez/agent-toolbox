# Contributing

This page is for people who change this repository. Agent rules live in
[`AGENTS.md`](../AGENTS.md).

## Layout

| Path | Holds |
| --- | --- |
| `plugins/swe/` | swe skills, the `comment-sicko` agent, the router and its playbooks, hooks, scripts, and the swe guide in `docs/` |
| `plugins/lab/` | lab skills and their scripts and references |
| `plugins/uni/` | tutoring skills, the teaching workspace, templates, and evaluations |
| `claude-mods/<mod>/` | Claude Code mods, one plugin per mod |
| `evals/skills/` | offline skill-activation evals ([README](../evals/skills/README.md)) |
| `.claude-plugin/marketplace.json` | the Claude catalog |
| `.agents/plugins/marketplace.json` | the Codex catalog |
| `.agents/skills/sync-pstack-upstream/` | the repo-local skill that syncs swe with upstream pstack, and its sync record |

## Versions

No manifest and no catalog entry has a `version` field, and
`.github/scripts/manifest_versions.py` fails CI when one does. Each host then
updates on a new commit:

- Claude Code uses the 12-character SHA of the newest marketplace commit as
  the version. Every commit to `main` is an update, also a docs-only commit.
- Codex reinstalls every plugin when the marketplace commit changes. It names
  the cache folder `1.0.0`.
- agy has no update command. `agy plugin install` again copies the new files.
- Hermes Agent keys on the commit SHA. A `--ref` install is pinned, so
  upgrade it with `hermes plugins install … --ref <new-sha> --force`.

A plugin has up to four manifests:

- `plugins/<plugin>/.claude-plugin/plugin.json`
- `plugins/<plugin>/.codex-plugin/plugin.json`
- `plugins/<plugin>/.antigravity-plugin/plugin.json`
- `plugins/<plugin>/plugin.json`, the Agent Plugins v1 manifest that Hermes
  Agent reads. Its `$schema` is
  `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`; check it with
  `hermes plugins validate plugins/<plugin>`.

A mod has the Claude manifest only.

Antigravity CLI (agy) reads plugin hooks only from `hooks.json` at the plugin
root, so it skips `hooks/hooks.json`. agy loads `rules/AGENTS.md` as a plugin
rule instead. That file is a copy of `hooks/session-start.md`, not a symlink,
because the skill-eval harness rejects symlinks. Edit both files together: the
`checks` workflow fails when they differ.

`agy plugin validate plugins/swe` reports errors for the agents in
`plugins/swe/agents/`. agy accepts only its own model tiers and a YAML list
for `tools`, so it skips these agents and loads the rest of the plugin. Keep
the Claude values (`model: opus`, `model: sonnet`, comma-separated `tools`):
changing them to suit agy changes which model Claude Code runs.

## Checks

The `checks` workflow also runs the tech-tree model check and the statechart
tests with the statechart skill's pinned TLC and Java. To run the statechart
tests with TLC locally, run `uv run .github/scripts/statechart_tlc.py`. It
installs both with mise and prints the `TLA2TOOLS` and `JAVA` values. Set
them, then run `npm test` in `plugins/swe/skills/statechart/scripts`. Without
`TLA2TOOLS`, the TLC tests skip.

The mod tests import `claude-code/testing`, so `bun test` and `node --test`
cannot run them. Run `claude plugin test claude-mods/<mod>` for each mod.

A broad plugin release runs the [release checks](release-checks.md). A repeated
agent mistake gets an enforcer from the `correct` skill, recorded in
[agent rule enforcers](agent-rule-enforcers.md).
