# Changelog — swe plugin

Newest first. Versions are the `version` field shared by
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`.
Before 1.9.3 the plugin was named `knack`; before 1.0.0 its contents lived in
the single `agentspec` plugin.

## Unreleased

- Fix the deterministic workable query for stacked runs: `linear_tracker.py`
  judged "already merged" against the integration branch, which mid-stack
  never receives changesets past the first (they land on `stack/<n>` branches),
  so dependents stayed blocked and the implement loop drained after the first
  changeset. The merge check now runs against the run's stack tip — the
  highest-numbered `stack/<n>` branch, else the integration branch. The
  swe-loop's agent-driven fallback query and the Linear reference also named
  the pre-rename `task/` branch prefix; both now say `change/`, matching the
  branches implementers actually create.

## 1.15.2 — 2026-08-10

ACP bridge protocol fidelity, six changes shipped as one stacked series:

- Graceful cancellation: cancelling a delegation now sends ACP
  `session/cancel` and gives the agent a 2s grace window to end the turn —
  a compliant agent returns its partial answer with
  `stopReason: "cancelled"` and its session stays continuable by
  `sessionId`; a non-compliant one is terminated exactly as before.
- Opt-in `--turn-timeout SECONDS` bridge option: bounds a hung
  `session/prompt` (permission round-trips included) and surfaces a named
  `TurnTimeout` error through the graceful-cancel path. Absent flag =
  unbounded, unchanged behavior; invalid values are startup usage errors.
- Chunk-streamed progress: agent message text now flows into MCP progress
  notifications, throttled by a deterministic 200-character interval, so
  long generations no longer look dead to stdio idle timeouts.
- Capability-gated session resume: an unknown `sessionId` on an agent that
  advertises `loadSession` is resumed via ACP `session/load`, with the
  model pin and session-mode selection reapplied and replayed history kept
  out of the answer and progress stream.
- Non-text content placeholders: non-text message blocks appear in the
  answer as `[<type> omitted]` instead of vanishing, so an image-only
  reply is no longer misreported as "The agent returned no message."
- Write-mode read parity and denial surfacing (user-directed
  permission-policy change): write mode now passes read-shaped tool kinds
  (`read`/`search`/`fetch`/`think`) without the workspace-containment
  check, matching what read-only mode always allowed — mutating kinds keep
  full containment — and a write-mode turn that streamed an answer while
  tool calls were denied carries an appended denial account instead of
  hiding the denials in `deniedToolCalls`.

## 1.15.1 — 2026-08-10

- Broaden `opencode-explorer` to web research: its description now advertises
  web searches, documentation and API lookups, current facts, and
  error-message research alongside repository sweeps, so orchestrators —
  which route on description text — send web questions to OpenCode instead of
  answering host-side. No new server: OpenCode's native `websearch`/`webfetch`
  already run under the explorer's read-only bridge policy, and a separate
  researcher forwarder would have been config-identical. `/implement` names
  the explorer as the web-research route on both hosts.

## 1.15.0 — 2026-08-10

- Remove Codex as a delegation target: the `codex-delegator` agent, the `codex`
  MCP server in `.mcp.claude.json`, and the `"codex"` value in the swe-loop
  `roles` map are gone. Codex delegation lives in the codex plugin; Codex as a
  *host* (the `.toml` agent twins, `.mcp.json`, native delegate calls) is
  unchanged.
- Make the skills provider-agnostic: host-specific "On Claude"/"On Codex"
  branches are now phrased by capability (named subagents vs direct delegate
  calls), and no skill names a model — the implement skill's per-role model
  matrix is replaced by role-altitude guidance, with pins living only in the
  agent definitions and MCP companion configs.
- Stop committing the `npx skills` self-install: `.agents/skills/` and
  `skills-lock.json` are untracked and gitignored (`.agents/plugins/` stays).
  opencode reaches the plugin skills through the `~/.agents/skills` symlinks
  `scripts/install.sh` already creates.
- Sanction workspace-planted symlinks in the ACP bridge's write policy: a path
  spelled inside the workspace is allowed even when a symlink (`docs/agents` →
  a vault dir) carries it elsewhere, so delegated spec and ADR writes stop
  coming back denied. Lexical escapes (`..`, the link target's own outside
  path) are still rejected.

## 1.14.0 — 2026-08-09

- Deliver the explorer, implementer, and reviewer OpenCode MCP servers natively
  with the Codex plugin. Codex resolves the bridge from the installed plugin
  root; Claude retains its existing forwarder agents, Codex delegator, and
  Workflow-conductor routing through a host-specific MCP companion.
- Route Codex's manual `/implement` path directly through the three namespaced
  `delegate` tools: read-only exploration, one bounded write delegation per
  changeset, then one read-only review of the assembled diff. Missing or failed
  requested tools remain loud; there is no host-model fallback or shell-out
  delegation path.
- Document the fresh-task runtime check that confirms all three Codex tools and
  completes a bounded explorer call. Host-normalized drift coverage keeps the
  two MCP companions on the same OpenCode model, effort, mode, argv, and
  timeout policy.

## 1.13.0 — 2026-08-08

- Add **OpenCode Go as an external worker provider**, through the existing ACP
  bridge (`opencode acp`) rather than a second delegation path. `implementer`
  and `reviewer` now default to it; `planner`, `publisher` and every
  deterministic step stay host-native.
- Pin one model per OpenCode role in `.mcp.json` — explorer on
  `deepseek-v4-flash`, implementer on `gpt-5.6-luna`, reviewer on
  `deepseek-v4-pro`, so review never shares the implementer's model. A pinned
  server serves a `delegate` tool with no `model` field, so the ids live in one
  manifest instead of in three prompts a subagent has to obey.
- Teach the bridge three flags: `--model` and `--effort` pin a server, and
  `--read-only-mode` selects the agent's own read-only session mode.
  OpenCode auto-approves edits inside the session cwd and never asks the
  client, so the permission policy alone would have let a read-only delegation
  write; escaping writes still arrive as permission requests, so the
  workspace-containment rule is unchanged. A bridge that cannot select the mode
  refuses the delegation rather than running it unprotected. Reasoning effort
  is a separate, model-dependent config option applied after the model, which
  is why the order is enforced rather than incidental.
- Pin the model on the conductor's unrouted plumbing calls (workable query,
  settle, escalation note, run summary). They inherited the host session's
  model, so the same run could settle a round on a different model each time.
- Remove the Copilot forwarder and its `.mcp.json` entry. The bridge it
  motivated stays and is now what OpenCode arrives through.
- Reject a `roles` entry naming a provider that has no forwarder for that role
  at launch, instead of failing mid-run.

## 1.12.0 — 2026-08-07

- Delegate to another provider through **typed tool calls instead of shell
  strings**. Each external provider is registered in the plugin's `.mcp.json`,
  so a delegation is a JSON schema the model fills rather than a command line it
  composes: no quoting, no sandbox-flag drift, no `timeout`/exit-code juggling,
  and session resume becomes an argument. Codex registers natively via
  `codex mcp-server`; Copilot arrives through the new `mcp/acp_bridge.py`.
- Add `mcp/acp_bridge.py`, translating an [Agent Client
  Protocol](https://agentclientprotocol.com) agent onto MCP. ACP is what
  Copilot, Gemini CLI and the Zed agents speak, so another such provider is one
  `.mcp.json` entry. The bridge answers the agent's permission requests itself,
  which is what makes `mode: read-only` true for a provider that has no
  OS-level sandbox: it rejects every mutating tool kind, including kinds ACP
  adds later, and in `write` mode rejects any path resolving outside the
  workspace. Streamed ACP events become MCP progress notifications, keeping a
  long delegation clear of the stdio idle timeout.
- Add the `copilot-delegator` agent and let `roles` route `planner`,
  `implementer`, `reviewer` or `publisher` to `copilot` as well as `codex`.
- Fix the forwarder agents' tool restriction. Both delegators declared
  `allowed-tools`, which is not a subagent frontmatter field — Claude Code
  ignored it and gave them every tool, so "never work the task yourself" was
  prose a forwarder could quietly disregard by answering from its own
  exploration. They now declare `tools` naming only their provider's MCP tools,
  and `tests/test_skill_drift.py` pins it. **The other six agents still declare
  `allowed-tools` and still run unrestricted**; correcting them changes what the
  loop's workers can do and is left as its own change.

## 1.11.0 — 2026-08-07

- Publish a run as a **stack of pull requests**, one per changeset, instead of
  one PR for everything. Each changeset settles onto its own branch cut from
  the branch below, so the branches nest and each PR bases on the one below;
  review and ship run from the top. A one-changeset run is unchanged — same
  branch, same single PR, no `gh stack`. `ship-pr` gains a stack mode
  (`gh stack link`, never `gh pr create` per branch; `gh stack merge --yes`,
  never `gh pr merge`) and a force-push carve-out scoped to published stacks.
  The conductor returns `{prUrls, …}` in place of `{prUrl, …}`.
- Hand one implementer a whole changeset rather than spawning one per task. A
  subagent costs its full context load, a worktree and a merge before it edits
  a line, so a sweep filing 41 findings across 7 milestones now costs 7
  implementers, not 41. Changesets are implemented in parallel and settled
  sequentially, so the stack costs no wall-clock. Deliberately uncapped: a
  changeset too large for one implementer is a spec that should have been
  split, and `/to-issues` now calls that split at slicing time.
- Settle the work hierarchy on **spec → changeset → task**, with **stack** for
  the published chain and **round** demoted to scheduling that never reaches a
  branch or an artifact. Recorded in the repo's `CONTEXT.md` glossary.
  Branches are `change/<ids>-<slug>` for the work and `stack/<n>` for what it
  lands on; the tracker still accepts the older `slice/` and `batch/` prefixes
  so a run already in flight resolves what it merged.
- Add the `block-agent-attribution` PreToolUse hook. `ship-pr` forbade agent
  attribution in prose and prose did not hold: session URLs and "Generated
  with" footers kept reaching commit messages, where they cannot be rewritten
  after a push. The hook inspects publishing verbs only (`git commit`,
  `git tag`, `gh pr|issue|stack`) plus any `--body-file` they name, and
  rejects the call rather than editing the text underneath the agent.

## 1.10.6 — 2026-08-06

- Replace `link-docs-agents.sh` with `symlink-worktree-shared-dirs.sh`: same
  job, wider scope. Links the main checkout's gitignored `artifacts`, `data`,
  and `docs/agents` into a git worktree, and additionally fires on
  `PostToolUse: EnterWorktree` (Session hooks don't re-fire when EnterWorktree
  switches the session mid-turn). Refuses to link anything git would track.
- Move `format-python.sh` from `scripts/` to `hooks/`: `scripts/` is for
  swe-loop conductor helpers; hook targets live beside `hooks.json`.

## 1.10.4 — 2026-08-01

- Tracker resolution hardening. The `Issue tracker:` pin may now live in
  `CONTEXT.md` as well as `AGENTS.md`/`CLAUDE.md` — the pin's home when
  `AGENTS.md` is a shared global file — and `/to-issues` gains an auto-detect
  rung that reads prior specs' `tracker:` frontmatter before any capability-
  or hosting-based guess. `/start-loop`'s container step now resolves the
  tracker through `/to-issues`' ladder instead of assuming it, closing the
  gap that let a run land slices on the wrong tracker.
- Clear remaining `ty` type diagnostics.

## 1.10.3 — 2026-08-01

- Make hook commands fish-safe: `${CLAUDE_PLUGIN_ROOT}` becomes
  `"$CLAUDE_PLUGIN_ROOT"`. Neither harness string-substitutes shell-form hook
  commands — both export the variable and let a shell expand it — and Codex
  runs hooks through the login shell, where fish rejects `${VAR}` as a syntax
  error, killing the format-python hook on every `.py` write.

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
