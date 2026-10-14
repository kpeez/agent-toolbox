# lab

This page is for people who use the `lab` plugin for research and
experiments.

| Skill | Use for |
| --- | --- |
| `research` | One cited memo for a bounded question or a source audit |
| `deep-research` | A multi-lane research program with briefs, lane evidence, and an audited report |
| `autoresearch` | A bounded experiment loop against an approved metric and evaluator, and its cleanup |
| `making-plots` | Publication-quality result figures and their plotting code |
| `visualizing-data` | Review plots for honest scales and accessibility |

Start a skill by name, for example `/lab:research <question>` in Claude Code
or `$lab:research <question>` in Codex.

## Autoresearch files

A new run keeps its program, ledgers, logs, configuration, and figures under
`artifacts/autoresearch/<tag>/` in the repository. A configured vault gets the
closeout notes and only the figures those notes embed.
