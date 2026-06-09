---
name: blueprint
description: "Examples-based development — verify a planned implementation with a runnable example that imports the real repo, then graft the working slice into the codebase (or throw it away if it only answered a design question). Use to de-risk an approach before committing, sanity-check a data model, or try implementation ideas against real code. Triggers: 'blueprint this', 'prototype', 'spike', 'let me play with it', 'try a few designs'."
---

# Blueprint

A blueprint is **runnable code that proves a planned implementation before you
commit to it** — written against the real repo, not a sandbox reconstruction.
Import as much of the actual codebase as possible, build the smallest component
that exercises the idea end-to-end, and watch it work (or fail) for real. For
ML/research this is the default loop: try the approach in a scratch entry point
wired to real code, see whether it holds up, then keep what works.

Two endgames:

- **Promote** (default) — the blueprint validated a real implementation. Lift the
  working slice into the codebase where it belongs and delete the scaffold around
  it. The blueprint _becomes_ the implementation.
- **Throwaway** — the blueprint only answered a design question ("does this state
  model feel right?"). Capture the verdict, delete the code.

For a _long-running, autonomous_ exploration with a metric target and many
experiments, use `lab:autoresearch` instead — it manages worktrees, named
experiment groups, and result logging. Use `blueprint` for a question you resolve
in one sitting.

## Identify the question

From the prompt, the surrounding code, or by asking if the user is around:

- **"Will this implementation actually work?"** → import the real modules and
  write a small runnable example that drives the planned code path with real
  inputs. Promote the slice once it's green.
- **"Does this logic / state model / approach feel right?"** → build a tiny
  interactive script that pushes the model through cases hard to reason about on
  paper. Surface the full relevant state after every action. Usually throwaway.
- **"What should this look like?"** → generate a few radically different
  variations on one throwaway entry point, switchable with a flag, so they can be
  compared side by side.

If genuinely ambiguous and the user isn't reachable, default to whichever matches
the surrounding code and state the assumption at the top of the blueprint.

## Rules

1. **Import the real repo.** The point is to exercise real types, real data, and
   real call sites — not a toy reconstruction. The more of the actual codebase the
   example imports, the more its result means. These are NOT unit tests; they're
   executable demonstrations that a planned implementation works against the code
   that already exists.
2. **Runnable, named for the behavior.** Self-contained, exits 0 on success /
   non-zero on failure, prints what it checks and the result. Name it after the
   behavior it proves (`verify_replay_buffer_sampling.py`), not `example.py`,
   `test.py`, or `basic_usage.py`.
3. **Red before green (promote mode).** A promote-mode blueprint should fail first
   — the implementation doesn't exist yet — then pass once you write it.
4. **One command to run.** Whatever the project's task runner supports
   (`python <path>`, `uv run <path>`, `pnpm <name>`). The user starts it without
   thinking.
5. **Clearly marked, no polish.** Put it next to the module it blueprints so
   context is obvious, but name it so a casual reader sees it's scaffolding, not
   production. Obey existing conventions; don't invent new top-level structure. No
   persistence by default — if the question needs a store, hit a scratch DB/file
   named "BLUEPRINT — wipe me". No tests on the scaffold, no error handling beyond
   what makes it runnable, no abstractions.
6. **Surface the state.** Print/render the full relevant state on every action or
   variant switch so the user can see what changed.

## Verifying

The examples are the record — rerun them to confirm the red→green state. Don't
keep a separate run log. For tracker-linked work, paste the run result into the
issue comment when it matters for handoff.

## When done

- **Promote:** graft the validated slice into the codebase where it belongs and
  delete the scaffolding. If the example still verifies behavior end-to-end, it
  can survive as a spec example under `specs/<feature>/examples/`.
- **Throwaway:** capture the answer somewhere durable with the question it
  answered. If it's a durable design decision (hard to reverse, surprising, a real
  trade-off), record an ADR in `docs/adr/` (see `grill-me`'s `ADR-FORMAT.md`).
  Otherwise note it in the relevant spec's `SPEC.md` Decisions section or the
  tracker issue. Then **delete** the code — don't leave it rotting in the
  repo. If the user is around the capture is a quick conversation; if not, leave a
  placeholder with the question so the verdict can be filled in before deletion.
