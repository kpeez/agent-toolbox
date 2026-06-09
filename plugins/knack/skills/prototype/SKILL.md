---
name: prototype
description: Build a throwaway prototype to answer a design question before committing to it — a runnable script/app for state and logic questions, or quick variations for shape questions. Use when the user wants to prototype, sanity-check a data model or approach, explore options, or says "prototype this", "let me play with it", "try a few designs".
---

# Prototype

A prototype is **throwaway code that answers a question**. The question decides
the shape. For ML/research work this is the default mode: try an approach in a
scratch script, see whether it holds up, capture the verdict, delete the code.

For a *long-running, autonomous* exploration with a metric target and multiple
experiments, use `lab:autoresearch` instead — it manages worktrees, named
experiment groups, and result logging. Use `prototype` for a single quick
question you'll resolve in one sitting.

## Identify the question

From the prompt, the surrounding code, or by asking if the user is around:

- **"Does this logic / state model / approach feel right?"** → build a tiny
  interactive script that pushes the model through cases that are hard to reason
  about on paper. Surface the full relevant state after every action.
- **"What should this look like?"** → generate a few radically different
  variations on a single throwaway route/entry point, switchable with a flag, so
  they can be compared side by side.

If genuinely ambiguous and the user isn't reachable, default to whichever matches
the surrounding code and state the assumption at the top of the prototype.

## Rules

1. **Throwaway from day one, clearly marked.** Put it next to the module/page
   it's prototyping for so context is obvious, but name it so a casual reader sees
   it's a prototype, not production. Obey the project's existing conventions;
   don't invent new top-level structure.
2. **One command to run.** Whatever the project's task runner supports
   (`python <path>`, `uv run <path>`, `pnpm <name>`). The user starts it without
   thinking.
3. **No persistence by default.** State lives in memory. If the question itself
   involves a database, hit a scratch DB/file clearly named "PROTOTYPE — wipe me".
4. **Skip the polish.** No tests, no error handling beyond what makes it runnable,
   no abstractions. Learn fast, then delete.
5. **Surface the state.** Print/render the full relevant state on every action or
   variant switch so the user can see what changed.

## When done

The **answer** is the only thing worth keeping. Capture it somewhere durable
along with the question it answered:

- If the answer is a durable design decision (hard to reverse, surprising, a real
  trade-off), record an ADR in `docs/adr/` (see `grill-me`'s `ADR-FORMAT.md`).
- Otherwise note it in the relevant spec's `SPEC.md` Decisions section or its
  `STATUS.md` Context.

Then **delete or absorb** the prototype — fold the validated decision into real
code, or remove it. Don't leave it rotting in the repo. If the user is around,
the capture is a quick conversation; if not, leave the placeholder with the
question so the verdict can be filled in before deletion.
