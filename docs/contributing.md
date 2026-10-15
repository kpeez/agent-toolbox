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

Set each plugin's version by hand in both manifests, and keep them the same:

- `plugins/<plugin>/.claude-plugin/plugin.json`
- `plugins/<plugin>/.codex-plugin/plugin.json`

A mod has the Claude manifest only. Bump the patch number by default.

## Checks

A broad plugin release runs the [release checks](release-checks.md). A repeated
agent mistake gets an enforcer from the `correct` skill, recorded in
[agent rule enforcers](agent-rule-enforcers.md).
