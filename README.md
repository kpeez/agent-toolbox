# agent-toolbox

`agent-toolbox` provides two portable plugins for AI coding agents:

- **SWE** — spec-driven workflows and skills for sharpening, writing specs,
  tracking implementation work, reviewing changes, and shipping.
- **Lab** — source-backed research, reproducible experiment loops, and
  data-visualization guidance.

## Install

### Claude Code

```text
/plugin marketplace add kpeez/agent-toolbox
/plugin install swe@agent-toolbox
/plugin install lab@agent-toolbox
```

### Codex CLI

```text
codex plugin marketplace add kpeez/agent-toolbox
codex plugin add swe@agent-toolbox
codex plugin add lab@agent-toolbox
```

### Optional skills.sh skill-only install

```bash
npx skills@latest add kpeez/agent-toolbox
```

This installs editable skills only. Plugin agents and hooks still require a
plugin installation.

llmOS is maintained separately in
[kpeez/llmos-vault](https://github.com/kpeez/llmos-vault).

## Layout

- `plugins/swe/` — SWE skills, agents, hooks, and optional native tracker workflows.
- `plugins/lab/` — Lab skills and their runtime scripts and references.
- `.claude-plugin/marketplace.json` — Claude marketplace catalog.
- `.agents/plugins/marketplace.json` — Codex marketplace catalog.

## Versioning

Update each plugin's version manually in both manifests, and keep the values
identical:

- `plugins/<plugin>/.claude-plugin/plugin.json`
- `plugins/<plugin>/.codex-plugin/plugin.json`
