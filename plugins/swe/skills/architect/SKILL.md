---
name: architect
description: "Sketch types, signatures, and module structure in parallel competing designs before code, then stay in the loop while implementation fills in. Use for 'architect this', or code that crosses a function boundary where jumping to code would lock in the wrong shape."
disable-model-invocation: true
---

# Architect

Sketch types, function signatures, class shapes, and module boundaries with
`not implemented` bodies and pseudocode. Run competing designs in parallel,
synthesize across them, then fill in code against the chosen sketch.

Architect explores the design space before code that crosses a function
boundary. [codebase-design](../codebase-design/SKILL.md) stays the reference
for deep modules, its vocabulary, and the review of existing module
boundaries. Use its terms here. For a bounded design with one obvious shape,
its design mode is enough and architect is overkill.

A principle named here is a swe principle skill. Load it by reading
`../principle-<slug>/SKILL.md`.

## Start

Open the host's task list with one entry per phase before you start.

1. Ground
2. Sketch
3. Agree
4. Implement
5. Scrap

## Phase A: Ground the problem

Build a real mental model of every system the new code touches. Run the
[how](../how/SKILL.md) skill over the relevant subsystems. Naming a file is
not grounding. Produce the architectural explanation that `how` prescribes. If
the design redefines ownership or layering, also run the
[why](../why/SKILL.md) skill on the existing shape, so the rationale becomes a
constraint, not a guess.

Skip Phase A only when the work is greenfield with no surrounding system to
integrate.

## Phase B: Sketch

Run the [swarm](../swarm/SKILL.md) skill as a race with the `rank all` rule.
Give every runner the design-sketch task, the Phase A grounding artifacts, and
[the runner prompt](references/runner-prompt.md). Each runner works in its own
worktree, or in its own subdirectory under the sketch directory when no
worktree is available. What matters is independence between candidates.

Run at least two runners on different models. In Claude Code, run one on
`opus` and one on `sonnet`. For more diversity, add a runner on an external
provider the user named, through the
[orchestrate](../orchestrate/SKILL.md) external-provider mode. In Codex, vary
the reasoning effort, or add an external provider the same way.

Design it twice. Require at least two structurally distinct candidates before
synthesis, even when the first looks sufficient. This is the
**exhaust-the-design-space** principle made concrete. Compare whole-shape
alternatives, not point fixes inside one shape.

Screen every candidate against
[the design red flags](references/design-red-flags.md) before synthesis. Assume
the next contributor is an agent that sees only the files it opened, copies
the nearest example, and takes the shortest path that compiles. Prefer the
design where a change that looks right from one file is right for the whole
repo.

Compare viable candidates on interface depth, as
[codebase-design](../codebase-design/SKILL.md#vocabulary) defines it. Use the
comparison fields in
[interface design](../codebase-design/references/interface-design.md). Prefer
the design that hides more complexity behind a smaller, simpler public
surface. A rich interface can keep call chains short by concentrating
capability instead of scattering it across layers.

You are the judge. Pick one candidate as the base, graft what the others do
better, and reject the rest with a reason. Produce one synthesized design
package. Record the decision in the rationale's "Synthesis decision" section.

## Phase C: Agree (opt-in)

By default, go directly to implementation with the synthesized design. There
is no human checkpoint.

Add a checkpoint only when the invoker asks for one, such as "architect with
checkpoint" or "stop and show me before implementing". Then present the
synthesized design and pause for sign-off.

The synthesis can ship as its own commit either way, as the "scaffold first"
mode of the **foundational-thinking** principle. Planned and scoped breakage
during fill-in is fine, per the **outcome-oriented-execution** principle. For
adversarial pressure on the design before you implement, give the
synthesized sketch to a fresh reviewer subagent with the
[review brief](../../references/review-brief.md).

If the human pushes back on the shape, in a checkpoint or later, treat that as
Phase A evidence. Re-ground and run Phase B again before you write more code.

## Phase D: Implement against the sketch

Replace `not implemented` bodies with code, and pseudocode with logic. The
synthesized sketch is the contract. A deviation from it is a signal to report,
not friction to absorb silently. If a function needs a parameter the sketch
did not anticipate, ask whether the sketch was wrong, the requirement was
missed, or the implementation is overreaching.

## Phase E: Scrap when the architecture is wrong

If implementation keeps producing friction the sketch cannot absorb, throw the
sketch out. Do not bolt fixes onto a wrong design, per the
**redesign-from-first-principles** and **fix-root-causes** principles.

The signal is a pattern, not single instances. Tells:

- The same shape of workaround appears again and again across unrelated code.
- Several unrelated edge cases all need special-case branches.
- Types need escape hatches (`any`, casts, optional fields always set in
  practice) to compile.
- The "we need a lock" reflex appears when the sketch said the state was not
  shared.
- Callers must know the abstraction's internal rules to use it.
- Two or more independent Phase D deviations have the same shape.

Use judgment. A few edge cases do not condemn an architecture. Some problems
are complex. Complexity in the data is not complexity in the design.

When you scrap:

1. Run the [how](../how/SKILL.md) skill again over what has been built.
2. Redesign as if the new constraints had been day-one assumptions, per
   **redesign-from-first-principles**.
3. Subtract before you add, per the **subtract-before-you-add** principle. The
   new sketch must be smaller than the old one before it grows.
4. Return to Phase B and run the race again.

## Outputs

Write the caller's usage first and derive the type sketch from it. For a small
change, produce one file with the new types and signatures. For larger work,
produce a module map plus type definitions. The rationale ships alongside,
shaped by [the rationale template](references/rationale-template.md),
including the usage sketch and the synthesis decision.
