# agent-toolbox

`agent-toolbox` provides two portable plugins for AI coding agents:

- **SWE** — skills for sharpening and planning work, implementing and
  reviewing changes, and shipping pull requests.
- **Lab** — source-backed research, reproducible experiment loops, and
  data-visualization guidance.

SWE treats the merged pull request and the code as the record. Large work can
start from a short [plan](plugins/swe/skills/write-plan/SKILL.md) that hands off
to a fresh session and is mirrored to its Linear issue. Its
[implementation discipline](plugins/swe/skills/implement/SKILL.md) challenges
unnecessary code and simplifies the completed change before final verification.
Sound work can stay unchanged. Publication follows the user's authorization.

Lab keeps source checks and experiment boundaries while scaling research
artifacts and delegation to the question. Neither plugin requires a scheduler
or a separate workflow service.

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

This installs editable skills only. Plugin agents still require a
plugin installation.

## Project documents

ADRs, notes, and research default to `.agents/docs/`. Follow an explicit
project or user override. Create subdirectories as needed; the location may be
a regular directory or symlink, tracked or ignored. No setup step, vault, or
generated `AGENTS.md`/`CLAUDE.md` is required.

## Plans

Plans live in `<main checkout>/.agents/plans/`, shared by all worktrees. The
directory keeps itself out of git with its own `.gitignore`.

A plan named `ABC-123-short-slug.md` is mirrored one way to a document on
Linear issue ABC-123 by SWE's Stop hook
([`plan_sync.py`](plugins/swe/scripts/plan_sync.py)). It reads a Linear personal
API key from `LINEAR_API_KEY`, or else from `~/.config/swe/linear-api-key`
(mode 0600, honoring `XDG_CONFIG_HOME`), so no shell configuration is needed.
Without a key, or without an issue key in the name, plans stay local and nothing
is blocked.

## Layout

- `plugins/swe/` — SWE skills, agents, and the plan-sync hook.
- `plugins/lab/` — Lab skills and their runtime scripts and references.
- `.claude-plugin/marketplace.json` — Claude marketplace catalog.
- `.agents/plugins/marketplace.json` — Codex marketplace catalog.

## Versioning

Update each plugin's version manually in both manifests, and keep the values
identical:

- `plugins/<plugin>/.claude-plugin/plugin.json`
- `plugins/<plugin>/.codex-plugin/plugin.json`
