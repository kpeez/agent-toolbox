# agent-toolbox

A portable, spec-driven workflow and skill set for AI coding agents — one
source of truth across Claude Code, Codex CLI, Antigravity CLI, and GitHub
Copilot CLI[^1].

Three plugins, each documented in detail by its own README:

- [**swe**](plugins/swe/README.md) — the core: the spec-driven workflow
  skills and the capability agents; `/start-loop` has the lead itself dispatch
  and ship an approved spec end to end
- [**lab**](plugins/lab/README.md) — bounded and deep source-backed research,
  autonomous experiment loops, and data-visualization guidance
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

The Codex SWE plugin delivers its skills plus three native OpenCode role tools.
The Codex `.toml` capability agents still come from the manual script below.

#### Codex OpenCode smoke check

Tool registration is fixed when a task starts. After installing or upgrading
the plugin, start a **fresh Codex task** in a repository and confirm its tool
registry contains all three names:

- `mcp__opencode__explore`
- `mcp__opencode__implement`
- `mcp__opencode__review`

Then call `explore` with `task: "Return the repository name and the path to its
root README only."` and the repository's absolute path as `cwd`. The smoke
check passes only when the role tool returns that bounded answer successfully;
a missing tool, unresolved plugin-root path, ACP startup error, authentication
error, or model error is a failed check.

### skills.sh — any agent

The [skills.sh](https://skills.sh) installer copies editable skill files into
your project, no plugin harness required:

```bash
npx skills@latest add kpeez/agent-toolbox                     # pick skills and target agent
npx skills@latest add kpeez/agent-toolbox --skill start-loop
npx skills@latest add kpeez/agent-toolbox/plugins/swe      # one plugin's skills
npx skills@latest update                                    # refresh installed skills
```

Skills install as plain editable files (Claude Code: `.claude/skills/`, a
symlink to the shared `.agents/skills/` copy). They live in your project and
need no plugin harness, but re-running `add` or `update` rewrites them from
the source, so keep customizations in your own fork rather than the installed
copies. The install is skills-only: the `swe:*` agents, hooks, and MCP servers
are not copied, so `start-loop` and `implement` rely on one of the plugin
installs above (or the manual script below) being present on the same
machine.

### Manual install (Codex agents, opencode, Antigravity, Copilot)

```bash
./scripts/install.sh
```

| Target            | Installed to                                           |
| ----------------- | ------------------------------------------------------ |
| Codex agents      | `~/.codex/agents/*.toml`                               |
| opencode          | `~/.agents/skills/*` — plugin skills symlinked          |
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
| `start-loop`                    | Run an approved spec to a shipped PR — the lead dispatches implementers per task, gates and merges itself, then ships |
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
| `qmd`                           | Search local markdown knowledge bases with the `qmd` CLI                                                |
| `setup-repo`                    | Interview-driven repo setup — thin `AGENTS.md`, `CLAUDE.md` symlink, `docs/agents/` topology            |

### lab

| Skill           | Purpose                                                                                      |
| --------------- | -------------------------------------------------------------------------------------------- |
| `research`      | Investigate one bounded question against high-trust sources; write one cited private memo    |
| `deep-research` | Coordinate read-only evidence lanes; retain packets and produce one citation-audited synthesis |
| `autoresearch`  | Run reproducible experiment loops under an approved program and frozen evaluator             |
| `data-viz`      | Research-backed guidance for designing and critiquing charts and figures                     |

### llmos

| Skill            | Purpose                                                          |
| ---------------- | ---------------------------------------------------------------- |
| `maintain-llmos` | Maintain the shared llmOS Obsidian vault through its conventions |
| `setup-llmos`    | Diagnose and configure machine access to the llmOS vault         |
| `vault-cli`      | Route deterministic vault operations through the llmos-vault CLI |

## Workflow

The spine is **sharpen → spec → issues → implement → review → PR**.
`/start-loop <idea>` runs the approved-spec half as one resumable command: the
lead dispatches one implementer subagent per spec task, runs the verification
gates and merges itself with shell commands, then dispatches a single reviewer
before shipping one PR — no conductor process, no Workflow tool. Sharpening
and spec-writing happen in a prior session. The
[swe plugin README](plugins/swe/README.md) documents the workflow and the
agents in detail.

## Versioning

Each plugin's version lives in exactly two files, kept identical: its
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`. The marketplace
catalogs carry only names and paths — regenerate them with
`scripts/gen-marketplaces.py`, never hand-edit. Bump both manifests at once:

```bash
scripts/bump-plugin-version.sh swe 1.14.0
```

A bump is inert until it lands on master — both providers install from GitHub,
not the working copy.

[^1]: Inspired by Matt Pocock's [skills repo](https://github.com/mattpocock/skills)
