---
name: start-loop
description: Run or resume the swe-loop — triage the idea, settle the design (interactive or autonomous), pass the conditional approval gate, then launch the swe-loop conductor. Use only when the user explicitly invokes /start-loop.
---

# /start-loop — swe-loop runner

You own the interactive half: container, triage, design, gate, task, launch.
Everything after — implement → review → ship — belongs to the `swe-loop`
workflow script; you launch it and read its summary, never run those phases
by hand.

## Argument resolution

- `/start-loop` or `/start-loop <free-form idea>` → **new run.** Start at
  Container first.
- `/start-loop <slug>` or `/start-loop <path to a spec>` → **resume** that spec
  (see Resume below).

## First: restate the goal

Rewrite the user's request as an observable end state and set it with
**`/goal`**. If it diverges from their intent, surface the gap before anything
else runs.

Once the workflow is launched, it gives each agent its contract and handoff tuple.
Every **architect** or **implementer** *you* dispatch yourself — sharpen
alternatives, the spec draft, the manual fallback — still gets its own `/goal`:
one line, end state plus how it's verified. A task worker without one is a bug.
**Explorers are exempt**: a read has a question, not an end state.

## 1. Container first

Triage's verdict, the gate record, the run id, and the launch args all need
`containerId`, so resolve it on **every** run, new or resumed, before anything
else. A spec records its container in its own YAML frontmatter
(`tracker:`, `tracker_container:`) — that is the only machine-readable link,
and nothing writes an identity token into tracker bodies any more.

On a new run — or any spec whose frontmatter names no tracker — first resolve
which tracker per `/to-issues`' "Tracker" section; never infer it from where
the code is hosted. Only then open that tracker's reference.

Resolve it per the tracker reference's "Container identity" section. Where that
names a resolver command, run it and act on its exit code:

- **0** — it printed the container id; use it.
- **2** — the spec names a container that no longer exists, or several match
  ambiguously. **Stop and tell the user.** Never create a container on this
  code: that is exactly how a run makes a duplicate project.
- **3** — no container exists yet. Create one per `/to-issues`'s container
  conventions, then record it on the spec (`--set <id>`, or the reference's
  equivalent) so later runs resolve it directly.

## 2. Triage — the conditional gate policy

Evaluate all four criteria. The **decision** goes in the spec's frontmatter as
`execution_mode: autonomous | review-gated` — that is what a resumed run reads.
The rationale goes in a verdict comment on the container, for humans; nothing
parses it. Comment body, verbatim shape:

```
swe triage verdict: GATED | AUTONOMOUS
- unambiguous against the repo and docs/agents/adrs/: pass|fail — <why>
- estimated task count <= 6: pass|fail — <estimate>
- no destructive or irreversible surface (data migrations, deletions,
  external side effects): pass|fail — <why>
- no new external dependencies: pass|fail — <why>
```

**ANY fail → the gated path. ALL pass → the autonomous path.** A design that
contradicts an accepted ADR fails the first criterion. The threshold of 6 is
part of the policy and is stated in the comment. "Autonomous" is not
"unreviewed" — `execution_mode` records the decision and the verdict comment is
the audit record.

The verdict is written once per run. On a resumed run, honor the recorded
verdict instead of re-evaluating (see Resume).

## 3a. Gated path (any criterion failed)

1. `/sharpen` interactively with the user until the branches are resolved.
2. `/write-spec` — delegate the drafting to the **`swe:architect`** agent
   without asking first; the draft is the review material. You present it and
   the user confirms at the single spec-approval prompt.
3. On unambiguous approval, set `approved: true` in the spec's frontmatter.
   Silence, compaction, or an unrelated reply is **not** approval; a change
   request reopens sharpening.

Exact wording: [references/checkpoint-prompts.md](references/checkpoint-prompts.md).

## 3b. Autonomous path (all criteria passed)

No user prompt anywhere in this path.

1. **`swe:architect`** interrogates the idea against the code and the
   ADRs and returns the settled decisions — what the interview would have
   concluded.
2. **`swe:architect`** drafts the spec from those decisions.
3. You set `approved: true` in the spec's frontmatter yourself — the same field
   the manual gate writes — alongside `execution_mode: autonomous` (the gated
   path writes `review-gated`).
4. Comment the gate record on the container: auto-approved, the spec path, and
   a pointer to the triage verdict comment above it.

## 4. Task the spec

Splitting is yours, not the conductor's — you hold the spec context, and in
practice the tasks are often already on the tracker before a run starts.
Dispatch **`swe:planner`** (or the matching delegator when the user routed
`planner` to another provider) to run `/to-issues` against the approved spec: publish
every task into the container from step 1 with native blocked-by relations,
validating each drafted body with
`uv run <scriptsDir>/validate_artifacts.py issue -` before it posts. The container is
already resolved, so a resumed run or a container that already holds issues
covering the spec gets its existing tasks aligned and extended, never
duplicated.

Then verify the workable set before launching: at least one published task
must be workable (not done, unblocked, no `ready-for-human` label). An empty
set is a stop, not a launch — the conductor would spin its workable query on
nothing.

## 5. Launch the workflow

The conductor lives at the plugin root as `workflows/swe-loop.js`, so Claude
Code also registers it as the named plugin workflow `/swe:swe-loop`. Launch it
by invoking the **Workflow** tool with scriptPath
`${CLAUDE_PLUGIN_ROOT}/workflows/swe-loop.js` and args exactly
`{specPath, slug, containerId, baseBranch, scriptsDir, specText, tracker}` — the spec's
path, its slug, the container from step 1, the branch the run integrates into
and ships from (if you are on the default branch, create the feature branch
first and pass that), `scriptsDir`, the spec's `tracker:` value, and `specText`.

`specText` is the spec file's **entire text**, read verbatim. Read `specPath`
and pass what you read; never summarise it, and never pass a path in its place.
The conductor may route implementation and review to another provider (ADR-0006)
whose CLI is sandboxed to the repo workspace, and the spec sits under
`docs/agents/`, a symlink pointing out of the repo — so an agent given only the
path spends a denied tool call and then works against a guess. The conductor
embeds this text in every prompt that can be routed. It rejects a launch
without it.

`scriptsDir` is the **expanded absolute path** to the installed plugin's
`scripts/` directory — resolve `${CLAUDE_PLUGIN_ROOT}/scripts` to a real `/…`
path and pass that. The conductor's agents run the plugin's scripts from there
(validators, any query script the tracker reference names) and the target
repo does not contain them; their shells do not define `CLAUDE_PLUGIN_ROOT`,
so passing the literal `${CLAUDE_PLUGIN_ROOT}/scripts` string fails every
run that needs one. The conductor rejects a non-absolute value outright.

The conductor constructs the workable and settle commands from `tracker`,
`scriptsDir`, `containerId`, and `baseBranch`; do not pass a command string or
ask an agent to infer one from tracker documentation.

Optional `roles` overrides the conductor's default provider routing. By default
`implementer` and `reviewer` run on OpenCode Go and everything else stays on
Claude, so the machine needs `opencode` installed and an authenticated OpenCode
Go subscription: verify with `opencode providers list` before launching. Pass a
`roles` map only to change that — keys among `planner`, `implementer`,
`reviewer`, `publisher`, values `claude` or `opencode` (`opencode`
is valid for `implementer` and `reviewer` only, the two roles it has a
model-pinned forwarder for). `{"implementer": "claude"}` pulls implementation
back host-native. A provider that is missing or unauthenticated
is a stop, not a silent fallback to a more expensive one.

Those are the **launch args** — the conductor's own input. Each agent's prompt
then carries only the fields it needs; no agent receives the tuple verbatim.
Like every swe handoff they cross a context boundary carrying only
identifiers and artifact pointers — spec path, slug, container, integration
branch, scripts dir, optional issue — never the conversation.

Before launching, run
`uv run <scriptsDir>/validate_artifacts.py spec <specPath>` — a spec that
fails its frontmatter, status, or marker checks is a stop, not a launch.

After launch, record the run on the spec's frontmatter as `run_id: <id>` and
`base_branch: <baseBranch>`. The branch is recorded because a fresh session
resuming this run has no other way to recover which branch it integrates into,
and frontmatter keeps it machine-readable instead of buried in a comment.

**No Workflow tool on this host** (per ADR-0006) → say so
and fall back to the manual orchestration in `/implement`. That manual path calls the three plugin-delivered
OpenCode delegate tools directly for read-only exploration, one bounded write
assignment per changeset, and final read-only assembled-diff review. Name the
fallback; never improvise a substitute conductor or silently replace a failed
delegation with a host-native agent or shell command.

## Resume (given a slug or path)

Read the spec's `tracker:` and `tracker_container:` frontmatter first, then the
matching tracker reference and the spec.

**Triage is not re-run when it already has a verdict.** Read the spec's
`execution_mode` frontmatter; if it is set, that verdict stands for the whole
spec — a gated run stays gated no matter what a later session would judge. Only
when it is unset do you run triage (§2) at all.

Route on the approval field — three ways, deterministically:

```
spec=$(ls docs/agents/specs/[0-9][0-9][0-9][0-9]-<slug>.md 2>/dev/null | head -n1)   # or use the path given
if [ -z "$spec" ]; then echo "NO SPEC"
elif sed -n '/^---$/,/^---$/p' "$spec" | grep -q '^approved: true'; then echo "APPROVED: $spec"
else echo "IN DESIGN: $spec"; fi
```

- **APPROVED** → relaunch the workflow with the same args, re-reading
  `specText` from the spec file so a spec edited since the last launch takes
  effect. Take `baseBranch`
  and the run id from the spec's `base_branch` and `run_id` frontmatter; with
  neither recorded, derive `baseBranch` from the branch you are currently on and
  say in your reply that you did so. Pass the run id as `resumeFromRunId`, a
  **parameter of the Workflow tool invocation** — not a field inside `args`,
  where it is silently ignored. Even without a run id the resume is safe: the
  conductor reads what is already merged from git, so tasks finished on the
  branch are never redone.
- **IN DESIGN** → resume the design phase the recorded verdict routes to at the
  existing spec: the gated path reopens `write-spec` at the review gate, the
  autonomous path expands and stamps it.
- **NO SPEC** → resume design from its start under the recorded verdict.

## Escalation, not gates

Once the spec is approved, the workflow runs to completion without
prompting. Problems reach you as **data, after the fact**: the run summary
(`{prUrls, tasksCompleted, escalations}` — one URL per changeset)
plus the conductor's
per-issue escalation comments — never a live worker report.

1. Read the summary's `escalations` when the run returns; each carries its
   surviving findings verbatim, so check them against the spec's Scope before
   trusting that the run covered it.
2. **Resolve** anything answerable from the spec, ADRs, or codebase; log the
   decision as a comment on the issue; relaunch the workflow to pick it up. A
   logged judgment call beats a stalled loop.
3. **Interrupt the user only for**: a scope change, a spec contradiction, a
   blocking `ready-for-human` task, or a destructive/irreversible action.

Every resolution lands as an issue comment so a fresh session inherits the
decision trail.

## Fail loud

If the container cannot be created, the tracker cannot be reached, or a
required skill or agent (`/sharpen`, `/write-spec`, `/to-issues`,
`swe:architect`) cannot be activated, name it and
stop before changing state — do not improvise a substitute. `/implement` is not
on that list: on the Workflow host the conductor owns those phases, and
`/implement` is only the ADR-0006 fallback for hosts without the Workflow tool.
