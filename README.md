# agent-toolbox

A portable, spec-driven workflow and skill set for AI coding agents — one
source of truth across Claude Code, Codex CLI, Antigravity CLI, and GitHub
Copilot CLI[^1].

Three plugins, each documented in detail by its own README:

- [**swe**](plugins/swe/README.md) — the core: the spec-driven workflow
  skills, the capability agents, and the swe-loop conductor that ships an
  approved spec end to end
- [**lab**](plugins/lab/README.md) — research: autonomous experiment loops
  and data-visualization guidance
- [**llmos**](plugins/llmos/README.md) — tooling, hooks, and the
  `llmos-vault` CLI for the shared llmOS Obsidian vault

Shared provider-neutral instructions live in [AGENTS.md](AGENTS.md);
`scripts/install.sh` is the manual path for non-plugin providers.

## Installation

### Claude Code

```bash
/plugin marketplace add kpeez/agent-toolbox
/plugin install swe@agent-toolbox
/plugin install lab@agent-toolbox      # optional: research machines
/plugin install llmos@agent-toolbox    # optional: machines with the llmOS vault
```

### Codex CLI

```bash
codex plugin marketplace add kpeez/agent-toolbox
codex plugin add swe@agent-toolbox
codex plugin add lab@agent-toolbox
```

> Codex plugins deliver skills only; the Codex `.toml` subagents come from the
> manual script below.

### Manual install (Codex agents, Antigravity, Copilot)

```bash
./scripts/install.sh
```

| Target            | Installed to                                           |
| ----------------- | ------------------------------------------------------ |
| Codex agents      | `~/.codex/agents/*.toml`                               |
| Antigravity CLI   | `~/.gemini/AGENTS.md` + skills symlinked from the repo |
| Copilot CLI       | `~/.copilot/copilot-instructions.md`                   |
| Claude statusline | `~/.claude/cc_statusline.py`                           |

Re-run after updating agent-toolbox. Skill scripts need no install — skills run
them in place with `uv run`.

## Skills

Each skill's `SKILL.md` is the canonical contract; this table is just the map.
The per-plugin READMEs explain how the skills fit together. Skills follow the
[agentskills.io specification](https://agentskills.io/specification).

### swe

| Skill                           | Purpose                                                                                                 |
| ------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `start-loop`                    | Run/resume the swe-loop end to end — triage, design, approval gate, then the conductor ships the spec   |
| `sharpen`                       | Interview the user to stress-test a plan; cross-check the code, record ADRs                             |
| `write-spec`                    | Create a feature spec — a pure-markdown design draft proven by committed tests                          |
| `to-issues`                     | Publish a spec as vertical-slice tracker issues with blocked-by relations                               |
| `implement`                     | Orchestrate implementing a spec — prove behavior with `/tdd`, fan work out to agents                    |
| `tdd`                           | Functional-test discipline — scratch scripts in `tests/temp/`, survivors become committed tests         |
| `ship-pr`                       | Commit stable verified work as atomic commits, push, keep a draft PR current; `finalize` flips it ready |
| `diagnose`                      | Disciplined debugging — build a feedback loop, reproduce, hypothesize, instrument, fix                  |
| `codebase-design`               | Shared deep-module vocabulary — depth, seams, adapters, the deletion test                               |
| `improve-codebase-architecture` | Find deepening refactors — turn shallow modules into deep ones                                          |
| `merge-conflicts`               | Resolve conflicts by tracing each side's intent; verify with the project's checks                       |
| `research`                      | Investigate a question against primary sources; capture cited findings as markdown                      |
| `qmd`                           | Search local markdown knowledge bases with the `qmd` CLI                                                |
| `setup-repo`                    | Interview-driven repo setup — thin `AGENTS.md`, `CLAUDE.md` symlink, `docs/agents/` topology            |

### lab

| Skill          | Purpose                                                                  |
| -------------- | ------------------------------------------------------------------------ |
| `autoresearch` | Autonomous experiment loops with defined metrics and stop conditions     |
| `data-viz`     | Research-backed guidance for designing and critiquing charts and figures |

### llmos

| Skill            | Purpose                                                          |
| ---------------- | ---------------------------------------------------------------- |
| `maintain-llmos` | Maintain the shared llmOS Obsidian vault through its conventions |
| `setup-llmos`    | Diagnose and configure machine access to the llmOS vault         |
| `vault-cli`      | Route deterministic vault operations through the llmos-vault CLI |

## Workflow

The spine is **sharpen → spec → issues → implement → review → PR**.
`/start-loop <idea>` runs it as one resumable command: spec approval is the
last user prompt, after which the swe-loop conductor slices, implements,
reviews, and ships with no further prompting. The
[swe plugin README](plugins/swe/README.md) documents the spine, the agents,
and the conductor in detail, with diagrams.

## Versioning

Each plugin's version lives in exactly two files, kept identical: its
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`. The marketplace
catalogs carry only names and paths — regenerate them with
`scripts/gen-marketplaces.py`, never hand-edit. Bump both manifests at once:

```bash
scripts/bump-plugin-version.sh swe 1.9.7
```

A bump is inert until it lands on master — both providers install from GitHub,
not the working copy.

[^1]: Inspired by Matt Pocock's [skills repo](https://github.com/mattpocock/skills)
