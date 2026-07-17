---
name: start-loop
description: Run or resume the knack feature workflow (sharpen → write-spec → to-issues → implement) as one resumable command. Use only when the user explicitly invokes /start-loop.
---

# /start-loop — feature pipeline runner

Run the knack spine end to end: `sharpen` → `write-spec` → `to-issues` →
`implement`. You own sequencing, gates, and handoffs. Each phase skill owns its
own behavior — activate it by name; never inline its logic.

## Argument resolution

- `/start-loop` or `/start-loop <free-form idea>` → **new run.** Start at `sharpen`.
- `/start-loop <slug>` or `/start-loop <path to a spec>` → **resume** that spec
  (see Resume below).

Intended shape: sharpen → spec approval in one session, then `/clear`, then
`/start-loop <slug>` to resume. Everything the resume needs lives on disk (the
spec) and on the tracker (issue state) — the loop never carries the interview
conversation.

## First: restate the goal

Rewrite the user's request as an observable end state and set it with
**`/goal`**. If it diverges from their intent, surface the gap before any phase
runs.

Every **planner** and **doer** you dispatch gets its own `/goal`: one line, end
state plus how it's verified. A task worker without one is a bug — don't launch
it. **Explorers are exempt**: a read has a question, not an end state.

## Resume (given a slug or path)

Resolve the spec and route on the approval marker. Nothing else needs computing
here: once issues are published, the tracker — not this skill — owns which are
published, in progress, or done.

```
spec=$(ls docs/agents/specs/[0-9][0-9][0-9][0-9]-<slug>.md 2>/dev/null | head -n1)   # or use the path given
grep -Fxq '<!-- knack:spec-approved -->' "$spec" 2>/dev/null && echo "APPROVED: $spec" || echo "IN DESIGN"
```

- **APPROVED** → the design gates are already passed. Hand straight to
  `implement`; it resumes from the tracker. Before publishing anything, search
  the tracker for the `<!-- knack-spec: <repo>/<slug> -->` marker so you never
  create a duplicate parent.
- **IN DESIGN** (no approved spec) → resume design: reopen `write-spec` at the
  review gate if the spec exists, or `sharpen` if it doesn't.

## Phases

Activate each phase skill by name (host-native activation → ask the agent to
activate it → read the installed `SKILL.md` and follow it). Pass the handoff
identifiers forward: slug, repo identity, tracker parent id, active child.
Roles are the `/delegate` tiers.

| Phase | Who | What |
| --- | --- | --- |
| `sharpen` | main session (HITL) | Settle the design. May commission **planner** subagents for alternatives and `/deliberate` cases. Gate → spec. |
| `write-spec` | main session; drafting may go to a **planner** | Write `docs/agents/specs/NNNN-<slug>.md`. On approval, add `<!-- knack:spec-approved -->`. **Last user prompt.** |
| `to-issues` | one **planner** subagent | Read the approved spec cold; flag gaps to you *before* publishing; slice, publish parent (stamped `<!-- knack-spec: <repo>/<slug> -->`) + children; return the issue list. It slices itself — the spec is its only input; sub-delegating adds cold-start cost for nothing. No gate. |
| `implement` | fan-out: one unblocked child = one **doer** subagent | Each doer gets its own `/goal` + handoff payload (spec path, slug, parent id, issue id). Design-heavy slices go to a **planner** first. Repeat until every required child is done. No gate. |
| review + `ship-pr` | fresh context | Review the diff against the spec via `patch-reviewer`, then `/ship-pr`. |

Every handoff crosses a context boundary carrying only identifiers and artifact
pointers — never the conversation.

## Gates

Two gates, both during design: sharpen → spec, and spec approval. Only an
unambiguous approval advances; silence, compaction, or an unrelated reply is
**not** approval. A change request returns to the phase that produced the
artifact. **Spec approval authorizes everything downstream** — slicing,
publishing, and the loop to completion. Never ask "ready to publish?" or
"begin implementation?" — the approved spec already answered.
Exact wording: [references/checkpoint-prompts.md](references/checkpoint-prompts.md).

## Escalation, not gates

After spec approval, problems flow up — never pause the loop to ask:

1. **Worker blocked** → reports BLOCKED/NEEDS_CONTEXT to you with specifics.
   Workers never prompt the user.
2. **You resolve** anything answerable from the spec, ADRs, or codebase; log
   the decision as a comment on the issue; relaunch. A logged judgment call
   beats a stalled loop.
3. **Interrupt the user only for**: a scope change, a spec contradiction, a
   blocking `ready-for-human` slice, or a destructive/irreversible action.

Every resolution lands as an issue comment so a fresh session inherits the
decision trail.

## Fail loud

If a required phase skill (`sharpen`, `write-spec`, `to-issues`, `implement`)
cannot be activated, name it and stop before changing state — do not improvise
a substitute.
