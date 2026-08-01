# Changelog — swe plugin

Newest first. Versions are the `version` field shared by
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`.
Before 1.9.3 the plugin was named `knack`; before 1.0.0 its contents lived in
the single `agentspec` plugin.

## 1.10.1 — 2026-08-01

- Replace the test-per-goal quota with an evidence doctrine: goals are covered
  by evidence, not one test each. A goal whose failure is silent — wrong
  numbers, leaked data, a broken invariant — earns a committed test; several
  goals running through one end-to-end path share a single pipeline-level test;
  a goal whose failure is loud on the first real run is proven by the
  reproducible demo `/ship-pr` already requires in the PR. The quota was the
  rule while the quality guards were only advice, so agents backfilled a test
  per goal and shipped suites that restate the source. `tdd/references/tests.md`
  is rewritten around the categories that earn a test in any codebase — code
  boundaries, calculation correctness, behavior invariants, one end-to-end
  pipeline test — with the ML examples kept as instances rather than the frame,
  and its anti-pattern list extended with general-software theater (CLI arg
  parsing, restated validation, trivial serialization). `tdd/SKILL.md`,
  `implement/SKILL.md`, and `write-spec/templates.md` state the doctrine
  instead of the quota.

## 1.10.0 — 2026-07-31

- Stop managing run state in markdown comments. Nothing a resumed run reads is
  an HTML comment any more: approval (`approved`), triage outcome
  (`execution_mode`), run id, integration branch and the tracker container all
  live in the spec's YAML frontmatter; issue status lives on the tracker; and
  what a run has already merged is read from git (`git branch --merged` over
  `slice/<identifier>` branches), which cannot drift because it is the same
  fact the merge created. `<!-- knack:slice-complete -->` is gone entirely, and
  with it the escalation for a marker that failed to post — a failed tracker
  write is now cosmetic, because git decides what is merged. Comments keep only
  what humans read: triage rationale, progress notes, escalations.
- Keep the tracker honest while a run works. The loop advances issue state at
  the two moments it already touches the tracker (picked up → In Progress,
  merged → In Review) and reconciles the container's own status at the end, so
  a project can no longer sit in Backlog while its issues are merged and
  shipped. Nothing is ever marked complete by the loop: a run ends at a draft
  PR, not a merge.
- Replace hand-written Linear GraphQL with the `linear` CLI. `frontier.py` is
  now `linear_tracker.py` — the name says what it talks to — and lost its
  query, auth and pagination code in the process. It gained `container`, which
  resolves the project a spec publishes into from that spec's frontmatter with
  distinct exit codes for "none yet" and "the recorded one is gone" so a run
  can never create a duplicate project, and `sync` for container status. A
  `--backfill-all` sweep migrates specs published under the old
  `<!-- knack-spec: -->` body token; the resolver still reads that token, but
  nothing writes new ones.
- Rename the loop's confusing "frontier" vocabulary to "workable": the
  `frontierCmd` launch arg is `workableCmd`, agent labels are `workable:*`, and
  slice branches are `slice/<identifier>` (the old `knack/slice/` prefix is
  still recognised so in-flight runs resolve).
- Stop restating workability rules in every tracker reference. The conductor
  states them once; each reference now carries only its own mechanics, its
  container-identity convention, and its state-transition commands. The GitHub
  and local references had drifted to the pre-1.9.9 blocker rule and silently
  contradicted the conductor.

## 1.9.9 — 2026-07-30

- Let a blocked-by chain advance inside one run. A merged slice's tracker state
  does not change until the run's PR lands, but the frontier judged blockers by
  state alone — so after slice 1 merged, every slice depending on it stayed
  "blocked", the frontier drained, and the run shipped early. Both observed
  multi-slice runs hit this and needed one manual relaunch per dependency edge
  (four launches for one three-slice spec). The slice-complete marker the loop
  already posts on merge now counts as done on both sides: a marked issue is
  dropped from the frontier *and* satisfies anything it blocks. `frontier.py`
  applies the rules itself, so the frontier agent runs one command and returns
  its output instead of querying every issue's comments each round; the
  reference-driven prompt states the same rule for trackers without a command.
  `tests/test_frontier.py` covers it, including a three-slice chain draining one
  slice per round.
- Move slicing out of the conductor and into `/start-loop`. Across every
  observed run the launcher already had the slices on the tracker before
  launching (pre-existing issues aligned to the spec, or a resume) and passed
  `issueId` to skip the conductor's Slice phase — so the slicer agent never
  once executed, and the `issueId` launch arg's value was never read (its only
  effect was the skip). The launcher now dispatches the planner to run
  `/to-issues` (with `validate_artifacts.py` gating) and verifies a non-empty
  frontier before launch; the conductor starts at the frontier query, and the
  `issueId` launch arg is gone. A behavior test pins that the run's first
  agent call is the frontier, with no slicer.

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
