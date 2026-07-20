---
name: handoff
description: Write the session residue to the tracker so another model can take over mid-flight. Use when switching to a cheaper or different model, ending a session with work outstanding, or when the user runs /handoff.
---

# /handoff — hand the session across a model boundary

You are about to be replaced — by a cheaper model, a fresh chat, or nothing at
all — while work is still outstanding. Write down the part of this session that
isn't already written down, put it on the tracker, and stop.

This is not a status update. Status is the issue state (`/to-issues` owns that
vocabulary). This is the residue: what you learned that no artifact records.

## The one rule: you write it, not a subagent

**Never delegate this to a subagent.** A subagent starts cold — it did not
watch this session and cannot recover what happened in it. Handed a summarizing
task, it will reconstruct a plausible session instead of reporting the real
one, and the fabrication is invisible to the reader who needed the truth.

This is the exception to `/delegate`. Delegation pays off on token-heavy
_input_ — bulk reads, exploration, typing implementation. A handoff is
token-light output from context you already hold. Writing it yourself is both
cheaper and the only way to get it right.

## What already survives without you

Do not re-narrate these. Duplicating them creates a second source of truth that
drifts from the first, and the reader must then reconcile them.

| Already durable              | Where it lives                                     |
| ---------------------------- | -------------------------------------------------- |
| The design and its rationale | `NNNN-<slug>.md`                                   |
| What each slice must do      | the issue body                                     |
| What's done, what's blocked  | issue state + blocked-by links                     |
| What to work next            | the next unblocked child                           |
| Which files changed          | `git status`, `git diff`                           |
| Whether behavior works       | the tests named in the spec's Verification section |

If your handoff is mostly a Files Touched list, you have written `git status`
by hand. Delete it and start over.

## What only you have

Everything below died with the session unless you write it. Keep each entry to
a line or two, and include only what you actually hit — an empty section is a
fine section.

- **Ruled out** — an approach tried and abandoned, and the reason. Without
  this, the next model retries it at full price.
- **Gotcha** — a non-obvious constraint discovered the hard way, and the blast
  radius (which slices it touches).
- **Correction** — where the spec or an issue body is now wrong or stale, and
  what's actually true. Say it plainly; do not silently rewrite the spec.
- **In flight** — work started but not committed, and what state it's in.
- **Resume** — the concrete next action: the command to run, the issue to take.

## Where it goes

Never a local file. `STATUS.md` and other hand-rolled handoff files are the
ledger this workflow deliberately removed — status lives on the tracker, and a
handoff file drifts from it immediately. You may find `docs/agents/specs/NNNN-<slug>-handoff.md`
files already in `docs/agents/specs/` — those are legacy archives of the old status ledger
from before this workflow moved status to the tracker; read them for history,
but never create a new one.

Route by scope, using whichever tracker `/to-issues` selected (Linear MCP →
GitHub → local markdown):

- **Scoped to one slice** → comment on that child issue. `/implement` already
  reads the latest comment as the handoff before acting.
- **Spans slices, or no issue is active** → comment on the spec container — the
  Linear project or parent issue stamped `<!-- knack-spec: <repo>/<slug> -->`.
  Every slice reaches it from the rollup.
- **No tracker at all** (single-slice spec, one sitting) → say it in chat and
  tell the user it isn't durable. Do not invent a file to hold it.

## Workflow

<steps>
<step action="resolve">identify the active issue and its spec container; if the work isn't on a tracker, say so and skip to `report`</step>
<step action="filter">list what you know, then delete everything covered by the durable table above — what remains is the handoff</step>
<step action="verify">run the tests named in the spec's Verification section; paste the actual result, pass or fail. A claim about state that you did not just observe is a guess — mark it as one</step>
<step action="write">comment on the issue resolved above, one short section per non-empty category from "What only you have"; lead with Resume</step>
<step action="relabel">if you stopped because a decision needs a human, relabel the issue `ready-for-human` and say exactly what's needed</step>
<step action="report">tell the user where the comment landed and what the next model should be handed: the issue id, the spec path, and the resume command</step>
</steps>

## Handing off to a cheaper model

The receiving model does not need this session. It needs four identifiers and a
pointer — spec path, slug, container id, active issue id — exactly the payload
`/start-loop` passes to a doer. Give it those plus `/implement`, and it will
read the issue body as the brief and your comment as the handoff.

Resist pasting transcript. `/start-loop` puts it plainly: every handoff crosses
a context boundary carrying only identifiers and artifact pointers — never the
conversation. The transcript is what you are being paid to compress; shipping it
raw hands the cost straight back to the cheap model.
