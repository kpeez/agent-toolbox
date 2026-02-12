---
name: handoff
description: Capture session context before ending for seamless resume by next agent. Use when ending a session, switching contexts, or when user runs /handoff.
---

# /handoff - Session Handoff

Generate a handoff summary to ensure context continuity for the next session.

## Process

1. **Identify the active feature**
   - If argument provided, use that feature: `/handoff <feature-name>`
   - Otherwise, check `specs/` for the most recently modified implementation.md
   - If no specs, summarize the session work generally

2. **Gather session context**
   - What was accomplished, what's in progress or blocked
   - Files modified (check git status)
   - Gotchas or non-obvious context discovered

3. **Update implementation.md**
   - Move completed items to Done, update Next with pending items
   - Add new context, update Phase and Blocked status

4. **Update `specs/INDEX`** — sync this spec's row (phase, blocked, desc)

5. **Append to `specs/<feature>/handoff.md`**:
   ```markdown
   ## Session: <date>
   ### Completed
   - <what was done>
   ### In Progress
   - <what's partially done>
   ### Blocked
   - <blockers if any>
   ### Critical Context
   - <things the next session MUST know>
   ### Files Touched
   - <list of modified files>
   ### Resume Command
   <command or instruction to pick up where we left off>
   ```

6. **Confirm** handoff is complete and implementation.md is updated
