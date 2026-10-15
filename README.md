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

Start a new session after you install. To install the skills only, without
plugin agents, hooks, or the swe router, run
`npx skills@latest add kpeez/agent-toolbox`.

## Get started

Give the swe router a task with `/swe:swe-mode` (`$swe:swe-mode` in Codex):

```text
/swe:swe-mode the csv export drops its last row since yesterday's deploy. repro first, then fix and verify.
```

New here? Ask `/swe:help` which skill fits, or read the
[swe guide](./docs/guide/README.md). Each plugin README lists its skills.

## Docs

- [swe guide](./docs/guide/README.md): ten pages from setup to long runs.
- [Claude Code mods](./docs/mods.md): live panes for the Claude Code interface.
- [Contributing](./docs/contributing.md): how to change this repository.

## Credits

- The `swe` router, its playbooks and principles, and most `swe` skills adapt
  Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/99743e9c151c8537cbbf1f98bb38f34ef3368453/pstack).
  The [swe guide](./docs/guide/README.md) follows the layout of the pstack guide.
- Many `swe` skills, and `uni/skills/teach`, adapt Matt Pocock's
  [skills](https://github.com/mattpocock/skills).
- The `ship-pr` PR-body menu of visuals comes from Dex Horthy's
  [`show-me` skill](https://github.com/humanlayer/skills/blob/main/plugins/show-me/skills/show-me/SKILL.md).
- The audit mode of `swe/skills/testing-code` adapts the OpenClaw
  [test-audit skill](https://github.com/openclaw/openclaw/tree/80930af448ebabc84174146b56bc106d37fab3b4/.agents/skills/test-audit).
