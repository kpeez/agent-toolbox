# Changelog — swe plugin

Newest first. Versions are the `version` field shared by
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`.
Before 1.9.3 the plugin was named `knack`; before 1.0.0 its contents lived in
the single `agentspec` plugin.

## 1.9.8 — 2026-07-30

- Cut the loop's token cost roughly in half by removing duplicated reading, not
  capability. Measured on a real 35-agent run (55.9M cache reads against 302K
  output tokens — the spend is context re-reads, not generation): the same diff
  was reviewed three times (52% of the run) and each slice was merged and
  marked by its own pair of agents (15%). Now the code is reviewed **once**,
  assembled, through a single adherence lens, with a slice's own lint/types/
  tests as its pre-merge gate; one settle agent merges and marks a whole round
  in order; and surviving findings are fixed in place on the integration branch
  before re-slicing them onto the tracker is considered. The `missed`/`wrong`/
  `bloat` lens panel and the run summary's `cutList` are gone with it.
- Recreate the gitignored `docs/agents` symlink inside git worktrees:
  `hooks/link-docs-agents.sh`, wired on `SubagentStart` and `SessionStart`,
  mirrors the main worktree's link target so a slice worktree can read
  `docs/agents/specs|adrs|research` instead of silently seeing nothing. It
  resolves the target from the main worktree (no configuration), never fails a
  session, and removes its own link if the path is not gitignored.
- Distinguish "the reviewer found problems" from "the reviewer never ran": the
  assembled-review schema gains a `did-not-complete` verdict that is retried once
  and then escalated, consuming no fix round and never reaching a fix agent.
  The `codex-delegator` runs Codex in a background call under a 30-minute
  ceiling — the foreground `Bash` tool caps at 10 minutes, which is what killed
  a real high-effort review — and reports non-completion through the caller
  schema's non-completion channel.
- Take the model off the frontier query's critical path: a new optional
  `frontierCmd` launch arg runs the tracker's deterministic frontier command
  verbatim, and the frontier call retries with backoff on harness failures
  (the observed `529 Overloaded` deaths) instead of ending the run.
- Escalate honestly: the frontier failure reason carries the actual error text
  and appends the credential hint only when the error looks like auth, and an
  exhausted-fix-rounds escalation posts the surviving findings verbatim with
  `file:line` anchors so a resumed run does not start blind.

## 1.9.7 — 2026-07-29

- Make the swe-loop tracker-agnostic: the conductor's prompts no longer name
  Linear (GraphQL endpoint, `LINEAR_API_KEY`) and instead resolve the repo's
  tracker at runtime through the to-issues tracker references, which gain a
  "swe-loop frontier" section per tracker (Linear keeps `frontier.py`; GitHub
  and local markdown get equivalent procedures). A drift test pins the
  conductor and `/start-loop` to zero tracker mentions.

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
