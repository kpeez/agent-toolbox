---
name: implement
description: "How to implement a spec or feature: prove behavior before committing to it. Use whenever implementing a feature, bugfix, or behavior change."
---

# Implement

One verification discipline for the implementer that does one task.

## Prove behavior before you commit to it

**`/tdd`** is the discipline (the sketch -> graduate -> settle loop lives
there): goals are covered by evidence, not one test each. Silent failures earn
a committed test at caller altitude, written directly when the behavior is
known or graduated from a `tests/temp/` scratch script when it isn't; several
goals running through one end-to-end path share that pipeline-level test; a
goal whose failure is loud on the first real run is proven by the reproducible
demo `/ship-pr` already requires in the PR. A verdict-only script ends in a
recorded decision rather than a test. If you catch yourself calling a goal done
with nothing that verifies it, stop and produce the evidence; a red test, type
error, or lint failure is a stop, not a warning to note and continue past.

`/start-loop`'s run procedure owns dispatch, gating, and merging for a full
spec run; work tasks sequentially per the discipline below when implementing
outside that procedure, or on a host with no forwarder subagents.

### Manual fallback (no forwarder subagents)

On a host with no forwarder subagents (Codex), call the three plugin-delivered
OpenCode delegate tools directly. Every call names the absolute worktree root
as `cwd`:

- `mcp__opencode_explorer__delegate` with `mode: "read-only"` for
  repository exploration.
- `mcp__opencode_implementer__delegate` with `mode: "write"` for
  exactly one bounded write assignment per changeset.
- `mcp__opencode_reviewer__delegate` with `mode: "review"` for one
  read-only-plus-execute review of the complete assembled diff.

If a requested tool is missing, fails to start, or returns non-completion,
surface that result to whoever orchestrates you. There is no silent fallback
to a host-native agent or an `opencode run` shell-out.

## Implement one task

The discipline an implementer agent, or a developer working a single issue
directly, follows for one task. Never delegate this task further.

1. Read the issue body and its latest comment before acting.
2. Prove behavior per `/tdd`, sketching in `tests/temp/` when the design is
   uncertain.
3. Run verification gates in order: lint, types, tests. A failure at any gate
   stops the task; it is not a warning to note and continue past.
4. Comment tracker progress on the issue before you finish or run out of
   context. Write only the residue the session holds, leading with Resume:
   - **Resume** - the concrete next action.
   - **Ruled out** - approaches tried and abandoned, and why.
   - **Gotcha** - non-obvious constraints discovered the hard way.
   - **Correction** - where the spec or issue body is stale.
   - **In flight** - work started but not committed, and its state.
5. Report status to whoever orchestrates you: DONE, DONE_WITH_CONCERNS,
   NEEDS_CONTEXT, or BLOCKED. Escalation follows `/start-loop`'s policy; never
   prompt the user directly from a worker.

## Cross-references

- `/sharpen` - stress-test a plan before writing tests or scratch scripts.
- `/write-spec new <name>` - scaffold a pure-markdown spec whose Verification section names the tests.
