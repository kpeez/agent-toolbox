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
   - For legacy specs, update `implementation.md` instead

4. **Append to `specs/<feature>/handoff.md`**:
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

5. **Confirm** handoff is complete and `STATUS.md` is updated
