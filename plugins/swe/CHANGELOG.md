# Changelog — swe plugin

Newest first. Versions are the `version` field shared by
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`.
Before 1.9.3 the plugin was named `knack`; before 1.0.0 its contents lived in
the single `agentspec` plugin.

## 1.9.5 – 1.9.6 — 2026-07-29

- Add the `codex-delegator` agent: a thin forwarder that runs one bounded task
  through the local OpenAI Codex CLI and returns Codex's final answer verbatim.
- `/start-loop` gains an optional `roles` launch argument that routes loop
  roles (planner, implementer, reviewer, publisher) to Codex via the new agent.
- Restructure plugin layout: shared scripts (`format-python.sh`, `frontier.py`,
  `validate_artifacts.py`) consolidate under `scripts/`, and the loop conductor
  moves to `workflows/swe-loop.js`, where Claude Code also registers it as a
  named plugin workflow.

## 1.9.4 — 2026-07-29

- Retire three skills: zoom-out (never invoked), deliberate (folded into
  `/sharpen` as an inline decision rule), and handoff (its residue checklist
  now lives in `/implement`'s required progress comment).
- Extract `/codebase-design`: a single model-invoked source for the deep-module
  glossary and testability rules, referenced by `/improve-codebase-architecture`
  and `/tdd` instead of diverging copies.
- Make `/ship-pr` quasi-autonomous (fires proactively once branch work is
  verified) and require evidence-based PR bodies: reproducible commands with
  observed output and named tests, with gate runs banned as verification.
- Tune agent model defaults (architect pinned to Fable 5, per-role adjustments).

## 1.9.3 — 2026-07-28

- Rename the plugin from knack to swe, and the eng-loop workflow to swe-loop.
  All agents, skills, hooks, and scripts move to `plugins/swe/` unchanged.

## 1.9.1 – 1.9.2 — 2026-07-28

- Consolidate ten agents into six capability roles: architect, explorer,
  implementer, planner, publisher, reviewer (each with Claude and Codex
  variants).
- Delete the delegate skill and route roles to the native agents; replace the
  validate-skills script with a skill-drift pytest suite.
- Trim `/write-spec` duplication and scope the `/merge-conflicts` abort rule to
  its calling protocol.

## 1.9.0 — 2026-07-28

- Add the eng-loop: a Workflow-tool conductor that runs the whole spine
  (spec → issues → implement → review → PR) end to end, launched from
  `/start-loop` after spec approval.
- Gate the format-python hook on `*.py` paths via hook if-filters.

## 1.8.1 — 2026-07-20

- Linear tracker integration: represent a spec as a Linear project, guard
  against leaking private context into public repos, and tighten PR hygiene.

## 1.8.0 — 2026-07-17

- Skill-quality pass across the whole set; `/start-loop` resume logic
  simplified to one glob plus one grep on the spec approval marker.
- Teach the format-python hook to extract Codex apply_patch targets.

## 1.7.0 — 2026-07-17

- Delete the two hardcoded delegator agents; ext-subagent now picks its own
  provider, and the provider chain drops the redundant claude entry.

## 1.6.0 — 2026-07-16

- Move all agent-facing docs under a single gitignored `docs/agents/` symlink.
- Re-home spec completion onto the `/ship-pr` finalize step.
- Version resync as the llmos plugin joins both marketplaces.

## 1.5.0 — 2026-07-16

- Name specs `NNNN-<slug>.md` like ADRs; add the handoff skill; rename the pr
  skill to `/ship-pr`.
- Adopt the project-local docs layout for specs and ADRs.

## 1.4.1 — 2026-07-15

- Ship a PostToolUse hook that formats and lints edited Python files.
- Store ADRs outside the repo in the shared llmOS vault (migrating committed
  `docs/adr` content); rewrite `/tdd` around sketch-first functional tests.

## 1.4.0 — 2026-07-15

- Consolidate the blueprint and documentation skills into `/tdd`.

## 1.3.0 — 2026-07-15

- Rename orchestrate to `/start-loop`; spec approval becomes the last user
  gate before autonomous execution.
- Adopt the `SPEC-<slug>.md` naming convention and migrate spec storage to the
  shared llmOS vault path.

## 1.2.1 — 2026-07-15

- Reconcile the delegation tiers across skills, add ext-subagent tests, and
  wire review into the loop.

## 1.2.0 — 2026-07-15

- Introduce explorer/planner/doer delegation tiers with fan-out loop docs.
- Add the `/research` and `/merge-conflicts` skills.

## 1.1.2 — 2026-06-20

- Add the deliberate skill, rename grill-me to `/sharpen`, and revamp the
  skill set around the sharpened workflow.

## 1.1.1 — 2026-06-19

- Add documentation guidance and update agent setup.

## 1.1.0 — 2026-06-09

- Add the `/setup-repo` skill for repo-level agent instructions.

## 1.0.2 — 2026-06-09

- Revamp the spec workflow: lean specs, ADRs, and Pocock disciplines.
- Simplify skill setup and run delegating-work scripts via uv run.

## 1.0.1 — 2026-06-03

- Refactor spec status tooling, make the PR markdown artifact optional, and
  fix the STATUS.md frontmatter field used by the spec skill.

## 1.0.0 — 2026-06-02

- Initial release: the core-workflow half of the old agentspec plugin, carved
  out as knack when the marketplace was renamed agent-toolbox. Ships the spec,
  pr, ship, grill-me, qmd, handoff, delegating-work, agentic-development,
  adversarial-review, and using-linear skills plus the explorer/writer/
  reviewer agent files.
