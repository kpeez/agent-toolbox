---
name: figure-it-out
description: "Design a bespoke, auditable playbook when no swe playbook fits or the work is large: a migration, an ambitious multi-part change, or work a human reviews after stepping away. Scales rigor to the task, runs a hypothesis loop, and logs decisions."
argument-hint: "<task>"
disable-model-invocation: true
---

# Figure it out

When the task matches no playbook, design one. The deliverable before any code
is the workflow itself. It is a sequence of steps that scales rigor to the
task, runs the scientific method, and leaves a decision trail a human can
audit after stepping away.

A principle named here is a swe principle skill. Load it by reading
`../principle-<slug>/SKILL.md`.

## Steps

1. `1-read-principles`: Read the [Principles](../swe-mode/SKILL.md#principles)
   section of the swe-mode router. Load each principle before you apply it.
2. `2-frame-the-run`: Frame the run. See [Frame](#frame).
3. `3-design-the-playbook`: Design the workflow and write it as a playbook.
   See [Design the playbook](#design-the-playbook).
4. `4-run-the-loop`: Run each designed step as an experiment. See
   [Run the loop](#run-the-loop).
5. `5-keep-the-audit-trail`: Log each decision as its step lands. See
   [Keep the audit trail](#keep-the-audit-trail).
6. `6-verify-and-hand-back`: Check the whole against the predicate. See
   [Verify and hand back](#verify-and-hand-back).

## Frame

Ground first, then commit. Run [go-deeper](../go-deeper/SKILL.md) on the task
unless it already ran. Do not start the run until you can state:

- The definition of done as a falsifiable predicate, per the
  **prove-it-works** principle.
- The scope, quantified. Give rough units and effort, plus the blockers that
  grounding surfaced.
- The rigor level, biased high. Ink decisions (hard to reverse) and a high
  blast radius get more. Reversible low-stakes steps get less. Rigor is gates and artifacts,
  not "try harder".

Present the framing and tradeoffs before you commit to a long run. Reversible
work proceeds, per the **never-block-on-the-human** principle. A multi-hour
run earns one checkpoint.

## Design the playbook

Split the work into atomic, independently landable units. Sequence the
riskiest unknown first. Scaffold and verification come before features, per
the **foundational-thinking** principle.

- Build the verification harness before the work. Capture the baseline from
  the pre-change state, so the check reads as "old value vs new value".
- For an ink design decision (hard to reverse), add a step that runs
  [architect](../architect/SKILL.md). Skip it for mechanical work whose shape
  is already concrete. A second architect run over a settled design is
  over-engineering, per the **laziness-protocol** principle.
- Decide what fans out. Parallelize only across seams, through
  [swarm](../swarm/SKILL.md). Give
  each worker its own worktree or branch, per the
  **separate-before-serializing-shared-state** principle. Do not over-fan.
  Pick each worker's model by role. In Claude Code, use `opus` for judgment
  and the hardest code, `sonnet` for routine code, and `haiku` for mechanical
  edits. In Codex, set reasoning effort the same way.

Write the designed workflow in the swe playbook file format, so the
[swe-mode router](../swe-mode/SKILL.md#track) can track it. That file is what
the human reviews.

```text
# <slug>

Applies when: <one line>.

<Owner line, such as "You own the design. Plan, review, verify.">

1-step-handle: Step text. (skill-or-principle, other-name)
2-step-handle: Step text. (skill-or-principle)

Reply: <what the reply gives>.
```

- Each step is one line. Its handle is the step number and a short kebab-case
  verb phrase.
- The parentheses name what the step loads. Each name is a swe skill, a
  principle slug without the `principle-` prefix, `reviewer agent`, a playbook
  slug, or another plugin's skill such as `lab:autoresearch`.
- Rules that are not steps go in a short paragraph between the owner line and
  step 1.
- A code-changing playbook ends with a `publish-draft-pr` step (ship-pr).

Save the file in the session scratch directory. For a long run, commit it
beside the decision log so the reviewer reads it in the PR.

Then execute the design. Add one task per designed step to the host's task
list, copied byte for byte, between the `4-run-the-loop` and
`5-keep-the-audit-trail` tasks. Run each under the loop discipline below.
Write the log as each step lands, not all at the end.

## Run the loop

Each unit is an experiment. State the hypothesis, make the smallest change,
and measure against the predicate on the real artifact. Keep the change if it
advanced. Revert it if it did not. Apply the **sequence-verifiable-units**
principle. Verify each unit before you start the next, instead of batching
checks at the end.

- Verify by inspecting the artifact, never a self-report. When something
  passes too easily, suspect the observation method before the system.
- Pair delegated work with a judge, such as a `reviewer agent` with the
  [review brief](../../references/review-brief.md). If a worker games the
  gate, reset and harden the contract. If the gate itself is wrong, fix the
  gate in its own change rather than routing around it.
- A verdict is VERIFIED, NOT VERIFIED, or INCONCLUSIVE. Inconclusive is not a
  pass. Do not hide a negative.

## Keep the audit trail

Log the run with [log-decisions](../log-decisions/SKILL.md). This work is
usually ambitious enough to commit the log, so the reviewer can read it in the
PR. The log plus the diff lets the human come back and trust the work.

## Verify and hand back

Check the whole against the predicate on the real product, not only the
harness. Use the project's [verification skill](../verification-skill/SKILL.md)
or the real entry point. Encode any recurring correction as a gate, a lint
rule, a check, or a script, per the **encode-lessons-in-structure** principle
and the [correct](../correct/SKILL.md) skill.

## Reply

Give the playbook you designed, the rigor level and why, the decision log
path, what is verified against the predicate, and what is still open. End with
the "Steps" section that the swe-mode router defines, with this skill's
handles and every designed handle.
