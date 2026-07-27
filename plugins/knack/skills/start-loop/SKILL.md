---
name: start-loop
description: Run or resume the knack feature workflow — triage the idea, settle the design (interactive or autonomous), pass the conditional approval gate, then launch the knack-graph conductor. Use only when the user explicitly invokes /start-loop.
---

# /start-loop — feature pipeline runner

You are the **human layer**: container, triage, design, gate, launch. The
**graph layer** — slice → implement → review → ship — belongs to the
`knack-graph` workflow script; you launch it and read its summary, never run
those phases by hand.

## Argument resolution

- `/start-loop` or `/start-loop <free-form idea>` → **new run.** Start at
  Container first.
- `/start-loop <slug>` or `/start-loop <path to a spec>` → **resume** that spec
  (see Resume below).

## First: restate the goal

Rewrite the user's request as an observable end state and set it with
**`/goal`**. If it diverges from their intent, surface the gap before anything
else runs.

Inside a graph run the conductor gives each node its contract and handoff tuple.
Every **designer** or **implementer** *you* dispatch yourself — sharpen
alternatives, the spec draft, the manual fallback — still gets its own `/goal`:
one line, end state plus how it's verified. A task worker without one is a bug.
**Explorers are exempt**: a read has a question, not an end state.

## 1. Container first

Triage's verdict, the gate record, the run id, and the launch args all need
`containerId`, so on **every** run, new or resumed, first search the tracker for
the immutable `<!-- knack-spec: <repo>/<slug> -->` marker bound to this
repository. Found → reuse that container. Missing → create it per `/to-issues`'s
container conventions (Linear project, or parent issue), stamped with the same
marker; `/to-issues` dedupes on it later, so this never yields a second one.

## 2. Triage — the conditional gate policy

Evaluate all four criteria and record each one's pass/fail in a verdict comment
on the container (ADR-0005). Comment body, verbatim shape:

```
<!-- knack:triage -->
knack triage verdict: GATED | AUTONOMOUS
- unambiguous against the repo and docs/agents/adrs/: pass|fail — <why>
- estimated slice count <= 6: pass|fail — <estimate>
- no destructive or irreversible surface (data migrations, deletions,
  external side effects): pass|fail — <why>
- no new external dependencies: pass|fail — <why>
```

**ANY fail → the gated path. ALL pass → the autonomous path.** A design that
contradicts an accepted ADR fails the first criterion. The threshold of 6 is
part of the policy and is stated in the comment. "Autonomous" is not
"unreviewed" — the verdict comment, anchored by `<!-- knack:triage -->`, is the
audit record.

The verdict is written once per run. On a resumed run, honor the recorded
verdict instead of re-evaluating (see Resume).

## 3a. Gated path (any criterion failed)

1. `/sharpen` interactively with the user until the branches are resolved.
2. `/write-spec` — delegate the drafting to the **`knack:spec-writer`** agent;
   you present the draft and the user confirms at the checkpoint prompts.
3. On unambiguous approval, add `<!-- knack:spec-approved -->` to the spec
   exactly as today. Silence, compaction, or an unrelated reply is **not**
   approval; a change request returns to the phase that produced the artifact.

Exact wording: [references/checkpoint-prompts.md](references/checkpoint-prompts.md).

## 3b. Autonomous path (all criteria passed)

No user prompt anywhere in this path.

1. **`knack:design-critic`** interrogates the idea against the code and the
   ADRs and returns the settled decisions — what the interview would have
   concluded.
2. **`knack:spec-writer`** drafts the spec from those decisions.
3. You stamp `<!-- knack:spec-approved -->` yourself — the same marker the
   manual gate writes, so every existing grep keeps working — and set the
   spec's `Execution mode` section to `autonomous` (the gated path leaves the
   template default, `review-gated`).
4. Comment the gate record on the container: auto-approved, the spec path, and
   a pointer to the `<!-- knack:triage -->` verdict comment above it.

## 4. Launch the graph

Invoke the **Workflow** tool with scriptPath
`${CLAUDE_SKILL_DIR}/scripts/knack-graph.js` and args exactly
`{specPath, slug, containerId, baseBranch, scriptsDir, issueId?}` — the spec's
path, its slug, the container from step 1, the branch the run integrates into
and ships from (if you are on the default branch, create the feature branch
first and pass that), `scriptsDir`, and `issueId` only when resuming against
one already-published slice set.

`scriptsDir` is the **expanded absolute path** to the installed skill's
`scripts/` directory — resolve `${CLAUDE_SKILL_DIR}/scripts` to a real `/…`
path and pass that. The conductor's agents run `frontier.py` from there and the
target repo does not contain it; their shells do not define `CLAUDE_SKILL_DIR`,
so passing the literal `${CLAUDE_SKILL_DIR}/scripts` string fails every
frontier query. The conductor rejects a non-absolute value outright.

Those are the **launch args** — the conductor's own input. Each node's prompt
then carries the fields that node needs; no node receives the tuple verbatim.
Like every knack handoff they cross a context boundary carrying only
identifiers and artifact pointers — spec path, slug, container, integration
branch, scripts dir, optional issue — never the conversation.

After launch, comment the run id on the container as
`<!-- knack:run-id <id> base=<baseBranch> -->`. The branch is part of the
marker because a fresh session resuming this run has no other way to recover
which branch the run integrates into.

**No Workflow tool on this host** (non-Claude providers, per ADR-0006) → say so
and fall back to the manual orchestration in `/implement`'s "Orchestrate the
fan-out" section. Name the fallback; never improvise a substitute conductor.

## Resume (given a slug or path)

Read the tracker first (container marker search above), then the spec.

**Triage is not re-run when it already has a verdict.** Read the container's
`<!-- knack:triage -->` comment; if one exists, that verdict stands for the
whole spec — a GATED run stays gated no matter what a later session would
judge. Only when no verdict comment exists do you run triage (§2) at all.

Route on the approval marker — three ways, deterministically:

```
spec=$(ls docs/agents/specs/[0-9][0-9][0-9][0-9]-<slug>.md 2>/dev/null | head -n1)   # or use the path given
if [ -z "$spec" ]; then echo "NO SPEC"
elif grep -Fxq '<!-- knack:spec-approved -->' "$spec"; then echo "APPROVED: $spec"
else echo "IN DESIGN: $spec"; fi
```

- **APPROVED** → relaunch the workflow with the same args. Take `baseBranch`
  and the run id from the container's `<!-- knack:run-id <id> base=<branch> -->`
  comment; with no such comment, derive `baseBranch` from the branch you are
  currently on and say in your reply that you did so. Pass the run id as
  `resumeFromRunId`, a **parameter of the Workflow tool invocation** — not a
  field inside `args`, where it is silently ignored. Even without a run id the
  resume is safe: the conductor drops every issue whose comments carry
  `<!-- knack:slice-complete -->`, so slices finished on the branch are never
  redone.
- **IN DESIGN** → resume the design phase the recorded verdict routes to at the
  existing spec: the gated path reopens `write-spec` at the review gate, the
  autonomous path expands and stamps it.
- **NO SPEC** → resume design from its start under the recorded verdict.

## Escalation, not gates

Once the spec carries the marker, the graph runs to completion without
prompting. Problems reach you as **data, after the fact**: the run summary
(`{prUrl, slicesCompleted, escalations, cutList}`) plus the conductor's
per-issue escalation comments — never a live worker report.

1. Read the summary's `escalations` and `cutList` when the run returns.
2. **Resolve** anything answerable from the spec, ADRs, or codebase; log the
   decision as a comment on the issue; relaunch the workflow to pick it up. A
   logged judgment call beats a stalled loop.
3. **Interrupt the user only for**: a scope change, a spec contradiction, a
   blocking `ready-for-human` slice, or a destructive/irreversible action.

Every resolution lands as an issue comment so a fresh session inherits the
decision trail.

## Fail loud

If the container cannot be created, the tracker cannot be reached, or a
required skill or agent (`/sharpen`, `/write-spec`, `/to-issues`,
`knack:design-critic`, `knack:spec-writer`) cannot be activated, name it and
stop before changing state — do not improvise a substitute. `/implement` is not
on that list: on the Workflow host the conductor owns those phases, and
`/implement` is only the ADR-0006 fallback for hosts without the Workflow tool.
