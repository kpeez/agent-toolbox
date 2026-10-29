# agent-toolbox

Plugins of skills for AI coding agents, for Claude Code and Codex CLI. Install
the plugins you need. Each one works alone.

| Plugin | What it does |
| --- | --- |
| [`swe`](./plugins/swe/README.md) | A router that runs software work through playbooks, skills, and principles, and ends with evidence |
| [`lab`](./plugins/lab/README.md) | Cited research memos and reports, experiment loops, and plot guidance |
| [`uni`](./plugins/uni/README.md) | Interactive lessons with questions, recall, and exercises |

The [Claude Code mods](./docs/mods.md) add live panes for tool calls,
subagents, and the session.

## Install

Each plugin installs alone. Install the ones you need, then start a new
session.

Claude Code:

```text
/plugin marketplace add kpeez/agent-toolbox
/plugin install swe@agent-toolbox
/plugin install lab@agent-toolbox
/plugin install uni@agent-toolbox
```

Codex CLI:

```text
codex plugin marketplace add kpeez/agent-toolbox
codex plugin add swe@agent-toolbox
codex plugin add lab@agent-toolbox
codex plugin add uni@agent-toolbox
```

Skills only, with [`npx skills`](https://github.com/vercel-labs/skills), one
plugin per command:

```text
npx skills@latest add https://github.com/kpeez/agent-toolbox/tree/main/plugins/swe
npx skills@latest add https://github.com/kpeez/agent-toolbox/tree/main/plugins/lab
npx skills@latest add https://github.com/kpeez/agent-toolbox/tree/main/plugins/uni
```

The skills-only install has no hooks and no agents. Each plugin README gives
the update commands.

## Get started

Give the swe router a task with `/swe:swe-mode` (`$swe:swe-mode` in Codex):

```text
/swe:swe-mode the csv export drops its last row since yesterday's deploy. repro first, then fix and verify.
```

New here? Ask `/swe:help` which skill fits, or read the
[swe guide](./plugins/swe/docs/README.md). Each plugin README lists its skills.

## Docs

- [swe guide](./plugins/swe/docs/README.md): ten pages from setup to long runs.
- [Claude Code mods](./docs/mods.md): live panes for the Claude Code interface.
- [Contributing](./docs/contributing.md): how to change this repository.

## Credits

- The `swe` router, its playbooks and principles, and most `swe` skills adapt
  Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/0f77cd5dab1e006de02d6ad221d5620de026473a/pstack).
  The [swe guide](./plugins/swe/docs/README.md) follows the layout of the pstack guide.
- Many `swe` skills, and `uni/skills/teach`, adapt Matt Pocock's
  [skills](https://github.com/mattpocock/skills).
- The `ship-pr` PR-body template copies Matt Pocock's
  [`pr` skill](https://github.com/mattpocock/skills/blob/main/skills/engineering/pr/SKILL.md),
  which adapts Dex Horthy's
  [`show-me` skill](https://github.com/humanlayer/skills/blob/main/plugins/show-me/skills/show-me/SKILL.md).
- The audit mode of `swe/skills/testing-code` adapts the OpenClaw
  [test-audit skill](https://github.com/openclaw/openclaw/tree/80930af448ebabc84174146b56bc106d37fab3b4/.agents/skills/test-audit).
