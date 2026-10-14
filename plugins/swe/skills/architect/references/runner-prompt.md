# Architect runner prompt

The orchestrator passes this file to every parallel candidate runner during
Phase B. It fills in the variable inputs around it: the task, the Phase A
grounding artifacts, the isolated working directory, and the path to write
outputs. The working directory is a git worktree when one is available, and
otherwise a per-runner subdirectory under the sketch directory. What matters
is independence between candidates.

You are producing one candidate design in architect's parallel exploration.
Read the [architect](../SKILL.md) skill in full first. That is the workflow you
are inside. Output a candidate design package with a type sketch, function
signatures, a module map, and a prose rationale shaped by
[the rationale template](rationale-template.md).

Apply the following discipline. The orchestrator compares candidates on these
axes to pick a base. A principle named here is a swe principle skill. Read it
at `../../principle-<slug>/SKILL.md`, relative to this file.

- Caller's usage first. Write the README-style usage and two or three real
  call sites before the types, then derive the type sketch from them. The
  usage is the spec. The two must agree, so reconcile the sketch to the usage,
  not the reverse.
- Data structures first. Get the core types right and the code becomes
  obvious. Trace each dominant access pattern through the proposed structure.
  If the answer is "we will add a map, index, or cache later", the structure
  is wrong.
- Interface depth. Compare the capability hidden behind the public surface
  with the size of that surface, using the
  [codebase-design vocabulary](../../codebase-design/SKILL.md#vocabulary).
  Prefer a simple interface that pulls complexity into the callee, even when
  the implementation becomes less simple. Keep transport and wire types off
  the public API. Parse into domain types behind the interface.
- Shared state. If two actors might both write, ask "what happens?" If the
  answer is not "nothing", default to per-actor state with a merge at the read
  boundary, per the **separate-before-serializing-shared-state** principle.
- Make boundaries visible. Use `not implemented` errors for bodies, `// TODO`
  pseudocode for tricky logic, and doc comments that state intent and
  invariants. A reader can trace data from input to output by reading types
  and signatures alone.
- Encode invariants in types. Hard-to-misuse types beat runtime checks, and
  runtime checks beat prose comments, per the **encode-lessons-in-structure**
  principle.
- Validate at boundaries and trust types inside, per the
  **boundary-discipline** principle. Write business logic as pure functions.
  Keep the shell thin.
- One source of truth per invariant. Derive instead of sync.
- Idempotent state transitions where they apply, per the
  **make-operations-idempotent** principle. Ask what happens if the operation
  runs twice or crashes halfway.
- Short call chains. If tracing the flow needs more than three files, flatten
  the hierarchy, per the **laziness-protocol** and **minimize-reader-load**
  principles.

You are one of the parallel runners, each on a different model. Produce the
best design your model can make. Do not hedge against the others. Differences
between candidates are the signal used to pick a base and graft. Converging on
a safe-looking middle defeats the exploration.
