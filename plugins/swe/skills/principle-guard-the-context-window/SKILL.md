---
name: principle-guard-the-context-window
description: "When context fills up with large outputs, long files, repeated reads, or fan-out planning, route the bulk to subagents and keep only summaries in the main thread."
disable-model-invocation: true
---

# Guard the context window

Context overflow degrades reasoning, creates compression artifacts, and halts
progress.

- **Route bulk to subagents.** Send large outputs, long files, transcripts,
  traces, and broad searches to a subagent (the Agent tool in Claude Code, a
  subagent in Codex). Have it return a summary with file pointers, not the raw
  payload.
- **Keep summaries in the main thread.** Keep findings, decisions, and
  pointers there. Do not paste raw payloads back in.
- **Do not reread.** Note what a read established, and point back to it
  instead of reading the same file again.
- **Size phases and cap scope.** Limit the files per phase, set turn budgets,
  and account for the cost of each mechanism, such as a subagent's own
  startup reads.

[minimize-reader-load](../principle-minimize-reader-load/SKILL.md) is the human analog of this principle.
