---
name: setup-repo
description: Set up repository instructions, tracker conventions, and the private docs/agents directory. Use when setting up a new repo, or when the user asks to add AGENTS.md or CLAUDE.md to a project.
disable-model-invocation: true
---

# Set up repository instructions

Keep `AGENTS.md` a compact delta on user-level instructions: verified commands,
repository structure, recurring conventions, and links to canonical project
context. Preserve existing content and confirmed choices.

## Inspect before proposing

Read the current `AGENTS.md`, `CLAUDE.md`, README, relevant build configuration,
CI and task scripts. Inspect the Git root, remote, and existing document paths
and symlink targets. Use targeted reads; delegate a broad unfamiliar survey.

Discover commands from actual project configuration. A `pyproject.toml` does not
establish Ruff, Ty or uv; a `package.json` does not establish a package manager.
Resolve those from configured scripts, lockfiles and current conventions.
Record what was verified and what remains unavailable. Do not invent checks or
release/version rules from a directory name such as `.changeset`.

## Resolve only missing choices

- Reuse the tracker named in existing project instructions or an explicitly
  selected spec. If none is established, propose an available tracker and ask
  one focused question. Linear, GitHub, local Markdown and other supported
  trackers are valid. Tool availability is not permission to create external
  issues. Keep private agent process records off public issue lists unless the
  user explicitly chooses that destination. Mechanics live in `/to-issues`.
- Reuse a confirmed llmOS project mapping or the existing valid `docs/agents`
  symlink. For a new mapping, propose the repository basename and confirm the
  destination before creating it. Do not ask again for an established mapping.
- Present the concise commands, structure and conventions to add. Honor
  existing authorization; ask only for unresolved material choices. Modify
  only the relevant sections, without replacing unrelated instructions.

## Preflight the entire setup before writing

Keep project documents behind the gitignored `docs/agents/` symlink. For a new
mapping, `<project-dir>` is `<llmos-root>/projects/<confirmed-project>`.

- The project directory must be absent or an existing real directory.
- The repository `docs` parent and llmOS `projects` parent must be absent or
  real directories. Never replace a file or symlink to make room.
- `docs/agents` must be absent or an existing symlink resolving to the confirmed
  project directory. Verify that Git ignores it before creating a new link;
  add only the required ignore entry when setup is authorized.
- `CLAUDE.md` must be absent or already symlinked to `AGENTS.md`.
- A conflicting file, directory, broken link or legacy layout is a collision.
  Report it and leave the affected setup untouched; do not migrate `docs/adr`,
  `docs/specs`, `specs`, or `adrs`, or partially repair a collision.

After all paths pass, create only missing directories and links, then apply the
approved instruction edits. Preserve existing project documents. Do not install
or update hooks as part of setup. Verify resulting links and ignore behavior.

## Content to retain

Use only the sections the repository needs:

```markdown
## Commands

<Verified commands and any environment requirements.>

## Structure

<Relevant directories and their purpose.>

## Issue tracker

Issue tracker: <chosen tracker and necessary project/team details>.
<Existing state/label mappings only when needed.> Mechanics: `/to-issues`.

## Project context

Read `docs/agents/CONTEXT.md` for project context and canonical links.
Read relevant ADRs for rationale and check their status and applicability
against current code and user intent before relying on them.
```

The optional project context format is defined in
[../sharpen/CONTEXT-FORMAT.md](../sharpen/CONTEXT-FORMAT.md). Specs retain approved
intent; the tracker retains task state; ADRs retain significant reasoning.
Keep personal preferences with the agent and avoid duplicate journals.

Report what changed, what was verified, and any unresolved collision or choice.
