---
name: orchestrate
description: Run or resume the knack feature workflow (sharpen → write-spec → to-issues → implement) as one gated command. Use only when the user explicitly invokes /orchestrate.
disable-model-invocation: true
---

# /orchestrate — feature pipeline runner

Run the knack spine end to end as **one resumable command** with a human gate
between phases: `sharpen` → `write-spec` → `to-issues` → `implement`. You own
sequencing, gates, handoff identifiers, and resume; each phase skill owns its own
behavior — activate it by name, never inline its logic.

`/orchestrate <free-form text>` starts or resumes; `/orchestrate` with no argument
inspects state and resumes the first incomplete phase. No verbs to learn — resume
falls out of skip detection over durable artifacts.

## First: restate the goal

Before anything else, **rewrite the user's request in your own words as a clear,
observable end state** — what is true when this is done — and set it with
**`/goal`**. Lead every run from that restatement; if it diverges from the user's
intent, surface the gap now, not after a phase runs.

Carry the discipline down: **every worker or subagent you dispatch gets its own
`/goal`** — a one-line end state scoped to its slice, plus how it is verified. A
worker launched without a defined end state is a bug; don't launch it. This holds
for each phase skill you hand off to and for any delegated implementation slice
(see `/delegate`).

## Recompute state first

Run this block up front and read its output before deciding anything:

```!
repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "git root: unavailable"
    exit 0
}
cd "$repo_root" || exit 0

branch=$(git branch --show-current 2>/dev/null || true)
echo "git root: $repo_root"
echo "branch: ${branch:-detached}"
echo "status (short):"
git status --short 2>/dev/null || true

spec_paths=()
while IFS= read -r spec_path; do
    spec_paths+=("$spec_path")
done < <(find -H specs -mindepth 2 -maxdepth 2 -name SPEC.md -print 2>/dev/null)

candidate_slugs=()
if [ "${#spec_paths[@]}" -gt 0 ]; then
    while IFS= read -r spec_path; do
        candidate_slugs+=("$(basename "$(dirname "$spec_path")")")
    done < <(ls -1td "${spec_paths[@]}" 2>/dev/null)
fi

echo "candidate spec slugs by mtime: ${candidate_slugs[*]:-none}"

slug=${ORCHESTRATE_SLUG:-}
if [ -z "$slug" ] && [ -n "$branch" ] && [ -f "specs/$branch/SPEC.md" ]; then
    slug=$branch
fi
if [ -z "$slug" ] && [ "${#candidate_slugs[@]}" -gt 0 ]; then
    slug=${candidate_slugs[0]}
fi

if [ -n "$slug" ] && [ -f "specs/$slug/SPEC.md" ]; then
    echo "spec: specs/$slug/SPEC.md present"
    if grep -Fxq '<!-- knack:spec-approved -->' "specs/$slug/SPEC.md"; then
        echo "spec approved marker: present"
    else
        echo "spec approved marker: absent"
    fi
else
    echo "spec: specs/<slug>/SPEC.md absent"
    echo "spec approved marker: absent"
fi

tracker_line=$(grep -h '^Issue tracker:' AGENTS.md CLAUDE.md 2>/dev/null | sort -u || true)
echo "issue tracker: ${tracker_line:-unspecified}"
if command -v gh >/dev/null 2>&1; then
    echo "gh: available"
else
    echo "gh: unavailable"
fi
exit 0
```

Resolve state from durable artifacts — **never** a `STATUS.md` ledger:

| State | Durable evidence |
| --- | --- |
| `UNSETTLED` | Conversation, `docs/adr/`, `CONTEXT.md`; no approved spec |
| `SPEC_APPROVED` | `specs/<slug>/SPEC.md` contains an exact `<!-- knack:spec-approved -->` line |
| `ISSUES_PUBLISHED` | Tracker parent carries `<!-- knack-spec: <repo>/<slug> -->` and has children |
| `IMPLEMENTING` | Child issue state + latest progress comment show active work |
| `COMPLETE` | All required children are Done |

`SPEC.md` is authoritative before publication; the tracker parent and children are
authoritative after.

## Phases and handoffs

For each phase, activate the named skill (host-native activation → ask the agent
to activate it → read the installed `SKILL.md` and follow it). Pass the handoff
identifiers forward: resolved slug, repo identity, tracker parent id, active child.

1. **`sharpen`** — settle the design. Then gate → produce the spec.
2. **`write-spec`** — write `specs/<slug>/SPEC.md`. On approval, add the
   `<!-- knack:spec-approved -->` marker. Then gate → publish issues.
3. **`to-issues`** — publish parent + vertical-slice children; stamp the parent
   with `<!-- knack-spec: <repo>/<slug> -->`. Then gate → begin implementation.
4. **`implement`** — take the next unblocked `ready-for-agent` child, give the
   worker its own `/goal`, implement, update the tracker. Repeat until `COMPLETE`.

## Who runs each phase

Roles are the `/delegate` tiers — explorer, planner, doer:

- **`sharpen`** — main session. The interview and all gates are HITL and cannot
  be delegated; may commission **planner** subagents to draft plan alternatives
  and `/deliberate` advocate cases.
- **`write-spec`** — spec *drafting* may go to a **planner** given the sharpened
  decisions as input; the main session reviews and holds the approval gate.
- **`to-issues`** — mechanical slicing of an approved spec; delegate to a **doer**.
- **`implement`** — fan out: one unblocked child issue = one **doer** subagent,
  each launched with its own `/goal` and the handoff payload (spec path, slug,
  tracker parent id, issue id). Design-heavy slices go to a **planner** first.
- **review + `pr`** — run in a fresh context (fresh subagent or new session):
  review the diff against the spec via the `patch-reviewer` agent, then `/pr`.

Every phase handoff crosses a context boundary with only the handoff
identifiers and artifact pointers — never the conversation.

## Gates

One explicit question at each transition; only an unambiguous approval advances.
Silence, context compaction, or an unrelated reply is **not** approval; a change
request returns to the phase that produced the artifact. Publication and
implementation each need their own approval because they mutate external state.
Exact wording: [references/checkpoint-prompts.md](references/checkpoint-prompts.md).

## Skip detection & resume

Recompute on every invocation; skip phases whose durable evidence already exists,
and **never create a duplicate tracker parent** — search for the `knack-spec:`
source marker before creating one. Full ordered algorithm and the per-failure
resume table: [references/state-detection.md](references/state-detection.md).

## Fail loud

If a required phase skill (`sharpen`, `write-spec`, `to-issues`, `implement`)
cannot be activated, name it and stop before changing state — do not improvise a
substitute.
