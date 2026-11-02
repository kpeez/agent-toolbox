# Contributing

This page is for people who change this repository. Agent rules live in
[`AGENTS.md`](../AGENTS.md).

## Layout

| Path | Holds |
| --- | --- |
| `plugins/swe/` | swe skills, the `daedalus` agent, the router and its playbooks, hooks, scripts, and the swe guide in `docs/` |
| `plugins/lab/` | lab skills and their scripts and references |
| `plugins/uni/` | tutoring skills, the teaching workspace, templates, and evaluations |
| `claude-mods/<mod>/` | Claude Code mods, one plugin per mod |
| `evals/skills/` | offline skill-activation evals ([README](../evals/skills/README.md)) |
| `.claude-plugin/marketplace.json` | the Claude catalog |
| `.agents/plugins/marketplace.json` | the Codex catalog |
| `.claude/skills/align-swe-with-pstack/` | the repo-local skill that syncs swe with upstream pstack, and its sync record |

## Versions

Set each plugin's version by hand in all three manifests, and keep them the
same:

- `plugins/<plugin>/.claude-plugin/plugin.json`
- `plugins/<plugin>/.codex-plugin/plugin.json`
- `plugins/<plugin>/.antigravity-plugin/plugin.json`

A mod has the Claude manifest only. Bump the patch number by default.

Antigravity CLI (agy) reads plugin hooks only from `hooks.json` at the plugin
root, so it skips `hooks/hooks.json`. Instead, `rules/AGENTS.md` is a symlink
to `hooks/session-start.md`, and agy loads it as a plugin rule.

`agy plugin validate plugins/swe` reports errors for the agents in
`plugins/swe/agents/`. agy accepts only its own model tiers and a YAML list
for `tools`, so it skips these agents and loads the rest of the plugin. Keep
the Claude values (`model: opus`, `model: sonnet`, comma-separated `tools`):
changing them to suit agy changes which model Claude Code runs.

## Checks

A broad plugin release runs the [release checks](release-checks.md). A repeated
agent mistake gets an enforcer from the `correct` skill, recorded in
[agent rule enforcers](agent-rule-enforcers.md).
