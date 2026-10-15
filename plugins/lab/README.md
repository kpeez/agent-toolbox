# lab

lab adds research and experiment skills: cited memos and reports, bounded
experiment loops, and plot guidance.

## Install

Each plugin installs alone. Pick one way, then start a new session.

Claude Code plugin:

```text
/plugin marketplace add kpeez/agent-toolbox
/plugin install lab@agent-toolbox
```

Codex CLI plugin:

```text
codex plugin marketplace add kpeez/agent-toolbox
codex plugin add lab@agent-toolbox
```

Skills only, with [`npx skills`](https://github.com/vercel-labs/skills), for
Claude Code, Codex, and other agents that read Agent Skills:

```text
npx skills@latest add https://github.com/kpeez/agent-toolbox/tree/main/plugins/lab
```

This installs the lab skills and no other plugin. Install all of them, because
they read each other by path. Add `-g` to install for your user instead of
the current project.

To update:

- Claude Code: `claude plugin marketplace update agent-toolbox`, then
  `claude plugin update lab@agent-toolbox`.
- Codex: `codex plugin marketplace upgrade agent-toolbox`, then
  `codex plugin add lab@agent-toolbox` again.
- npx skills: `npx skills update`.

## Skills

| Skill | Use for |
| --- | --- |
| [`research`](./skills/research/SKILL.md) | One cited memo for a bounded question or a source audit |
| [`deep-research`](./skills/deep-research/SKILL.md) | A multi-lane research program with briefs, lane evidence, and an audited report |
| [`autoresearch`](./skills/autoresearch/SKILL.md) | A bounded experiment loop against an approved metric and evaluator, and its cleanup |
| [`making-plots`](./skills/making-plots/SKILL.md) | Publication-quality result figures and their plotting code |
| [`visualizing-data`](./skills/visualizing-data/SKILL.md) | Review plots for honest scales and accessibility |

Start a skill by name, for example `/lab:research <question>` in Claude Code
or `$lab:research <question>` in Codex.

## Autoresearch files

A new run keeps its program, ledgers, logs, configuration, and figures under
`artifacts/autoresearch/<tag>/` in the repository. A configured vault gets the
closeout notes and only the figures those notes embed.
