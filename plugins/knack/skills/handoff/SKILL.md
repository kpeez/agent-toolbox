---
name: handoff
description: Capture session context before ending for seamless resume by next agent. Use when ending a session, switching contexts, or when user runs /handoff.
---

# /handoff - Session Handoff

Generate a handoff summary to ensure context continuity for the next session.

## Process

1. **Identify the active feature**
   - If argument provided, use that feature: `/handoff <feature-name>`
   - Otherwise, check `specs/` for the most recently modified STATUS.md
   - Fall back to legacy `implementation.md` only when no `STATUS.md` exists
   - If no specs, summarize the session work generally

2. **Gather session context**
   - What was accomplished, what's in progress or blocked
   - Files modified (check git status)
   - Gotchas or non-obvious context discovered

3. **Update `STATUS.md`**
   - Move completed items to Done, update Next with pending items
   - Add new context, update Phase and Blocked status

4. **Regenerate project status**
   - Run `python3 skills/spec/scripts/spec_status.py --write` from the repo root when that script exists
   - If using an installed skill copy, run the equivalent `spec/scripts/spec_status.py --write` path

5. **Append a dated block to the `## Handoffs` section of `specs/<feature>/STATUS.md`** (newest last). Handoffs live in `STATUS.md`, not a separate file — for legacy specs that already have a `handoff.md`, keep appending there:

   ```markdown
   ### Session: <date>

   - **Completed:** <what was done>
   - **In progress / blocked:** <what's partial or stuck>
   - **Critical context:** <things the next session MUST know>
   - **Files touched:** <list of modified files>
   - **Resume:** <command or instruction to pick up where we left off>
   ```

6. **Confirm** handoff is complete and `STATUS.md` plus generated `specs/STATUS.md` are updated
