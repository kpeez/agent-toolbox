---
name: start-loop
description: Run or resume the knack feature workflow (sharpen → write-spec → to-issues → implement) as one resumable command. Use only when the user explicitly invokes /start-loop.
disable-model-invocation: true
---

# /start-loop — feature pipeline runner

Run the knack spine end to end: `sharpen` → `write-spec` → `to-issues` →
`implement`. You own sequencing, gates, handoffs, and resume. Each phase skill
owns its own behavior — activate it by name; never inline its logic.

## Argument resolution

- `/start-loop <slug>` where `specs/NNNN-<slug>.md` (or the legacy
  `specs/<slug>/SPEC-<slug>.md`) exists → that spec is the target. Run the
  state block below with `START_LOOP_SLUG=<slug>`.
- `/start-loop <issue id or url>` → fetch it, find its parent, resume from
  tracker state.
- `/start-loop <free-form idea>` → new run; start at `sharpen`.
- `/start-loop` (no argument) → recompute state and resume the first
  incomplete phase.

Intended session shape: sharpen → spec approval in one session, then `/clear`,
then `/start-loop` (or `/start-loop <slug>`) fresh. The state block
reconstructs everything from disk — spec, approval marker, tracker parent — so
the loop starts clean, carrying artifacts, never the interview conversation.

## First: restate the goal

Rewrite the user's request as an observable end state and set it with
**`/goal`**. If it diverges from their intent, surface the gap before any phase
runs.

Every **planner** and **doer** you dispatch gets its own `/goal`: one line, end
state plus how it's verified. A task worker without one is a bug — don't launch
it. **Explorers are exempt**: a read has a question, not an end state.

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

spec_file_for() {
    local match
    match=$(ls -1 specs/[0-9][0-9][0-9][0-9]-"$1".md 2>/dev/null | head -n1)
    if [ -n "$match" ]; then
        echo "$match"
    elif [ -f "specs/$1/SPEC-$1.md" ]; then
        echo "specs/$1/SPEC-$1.md"
    elif [ -f "specs/$1/SPEC.md" ]; then
        echo "specs/$1/SPEC.md"
    fi
}

slug_from_path() {
    local base
    base=$(basename "$1")
    case "$base" in
        [0-9][0-9][0-9][0-9]-*.md)
            base=${base#????-}
            echo "${base%.md}"
            ;;
        *)
            basename "$(dirname "$1")"
            ;;
    esac
}

spec_paths=()
while IFS= read -r spec_path; do
    spec_paths+=("$spec_path")
done < <(find -H specs -maxdepth 1 -name '[0-9][0-9][0-9][0-9]-*.md' -print 2>/dev/null; find -H specs -mindepth 2 -maxdepth 2 \( -name 'SPEC-*.md' -o -name SPEC.md \) -print 2>/dev/null)

candidate_slugs=()
if [ "${#spec_paths[@]}" -gt 0 ]; then
    while IFS= read -r spec_path; do
        candidate_slugs+=("$(slug_from_path "$spec_path")")
    done < <(ls -1td "${spec_paths[@]}" 2>/dev/null)
fi

echo "candidate spec slugs by mtime: ${candidate_slugs[*]:-none}"

slug=${START_LOOP_SLUG:-}
if [ -z "$slug" ] && [ -n "$branch" ] && [ -n "$(spec_file_for "$branch")" ]; then
    slug=$branch
fi
if [ -z "$slug" ] && [ "${#candidate_slugs[@]}" -gt 0 ]; then
    slug=${candidate_slugs[0]}
fi

spec_file=""
if [ -n "$slug" ]; then
    spec_file=$(spec_file_for "$slug")
fi
if [ -n "$spec_file" ]; then
    echo "spec: $spec_file present"
    if grep -Fxq '<!-- knack:spec-approved -->' "$spec_file"; then
        echo "spec approved marker: present"
    else
        echo "spec approved marker: absent"
    fi
else
    echo "spec: specs/NNNN-<slug>.md absent"
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

Slug precedence: `START_LOOP_SLUG` (the explicit argument) → branch-name match
→ most recent spec by mtime.

Resolve state from durable artifacts — **never** a `STATUS.md` ledger:

| State | Durable evidence |
| --- | --- |
| `UNSETTLED` | Conversation, `docs/adrs/`, `CONTEXT.md`; no approved spec |
| `SPEC_APPROVED` | `specs/NNNN-<slug>.md` (legacy: `specs/<slug>/SPEC-<slug>.md`) contains an exact `<!-- knack:spec-approved -->` line |
| `ISSUES_PUBLISHED` | Tracker parent carries `<!-- knack-spec: <repo>/<slug> -->` and has children |
| `IMPLEMENTING` | Child issue state + latest progress comment show active work |
| `COMPLETE` | All required children are Done |

`NNNN-<slug>.md` is authoritative before publication; the tracker parent and
children are authoritative after. (The state block also detects legacy
`specs/<slug>/SPEC-<slug>.md` and bare `SPEC.md` specs; new specs always use
`specs/NNNN-<slug>.md`.)

## Phases

Activate each phase skill by name (host-native activation → ask the agent to
activate it → read the installed `SKILL.md` and follow it). Pass the handoff
identifiers forward: slug, repo identity, tracker parent id, active child.
Roles are the `/delegate` tiers.

| Phase | Who | What |
| --- | --- | --- |
| `sharpen` | main session (HITL) | Settle the design. May commission **planner** subagents for alternatives and `/deliberate` cases. Gate → spec. |
| `write-spec` | main session; drafting may go to a **planner** | Write `specs/NNNN-<slug>.md`. On approval, add `<!-- knack:spec-approved -->`. **Last user prompt.** |
| `to-issues` | one **planner** subagent | Read the approved spec cold; flag gaps to you *before* publishing; slice, publish parent (stamped `<!-- knack-spec: <repo>/<slug> -->`) + children; return the issue list. It slices itself — the spec is its only input; sub-delegating adds cold-start cost for nothing. No gate. |
| `implement` | fan-out: one unblocked child = one **doer** subagent | Each doer gets its own `/goal` + handoff payload (spec path, slug, parent id, issue id). Design-heavy slices go to a **planner** first. Repeat until `COMPLETE`. No gate. |
| review + `pr` | fresh context | Review the diff against the spec via `patch-reviewer`, then `/pr`. |

Every handoff crosses a context boundary carrying only identifiers and
artifact pointers — never the conversation.

## Gates

Two gates, both during design: sharpen → spec, and spec approval. Only an
unambiguous approval advances; silence, compaction, or an unrelated reply is
**not** approval. A change request returns to the phase that produced the
artifact. **Spec approval authorizes everything downstream** — slicing,
publishing, and the loop to `COMPLETE`. Never ask "ready to publish?" or
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

## Skip detection & resume

Recompute on every invocation; skip phases whose durable evidence exists.
**Never create a duplicate tracker parent** — search for the `knack-spec:`
marker first. Full algorithm and per-failure resume table:
[references/state-detection.md](references/state-detection.md).

## Fail loud

If a required phase skill (`sharpen`, `write-spec`, `to-issues`, `implement`)
cannot be activated, name it and stop before changing state — do not improvise
a substitute.
