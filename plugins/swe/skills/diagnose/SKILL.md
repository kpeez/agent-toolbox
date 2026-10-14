---
name: diagnose
description: Investigate bugs and performance regressions using focused evidence. Use when asked to diagnose, debug, or explain a failure.
---

# Diagnose

Investigate the reported symptom with enough evidence to support the requested
outcome. Diagnosis and repair are separate outcomes: a request to diagnose or
explain does not authorize implementation edits. When repair is authorized,
diagnose first, then make the fix with [implement](../implement/SKILL.md).

Consult relevant `.agents/docs/adrs/` only when they bear on the behavior or
decision under investigation.

## Procedure

1. `1-state-exact-failure`: State the exact failure mode and the surface where
   it was seen. [Establish evidence](#establish-evidence) gives the detail.
2. `2-build-feedback-loop`: Build the fastest loop that reproduces the
   failure, or record why none exists.
3. `3-seed-from-history`: When you suspect a regression, seed hypotheses from
   the history of the failing area with [why](../why/SKILL.md).
4. `4-rank-hypotheses`: Rank falsifiable hypotheses and change one variable
   per probe until one survives, as [Test hypotheses](#test-hypotheses) says.
5. `5-label-confidence`: Label the cause as
   [Label the cause](#label-the-cause) says.
6. `6-remove-instrumentation`: Remove task-owned temporary instrumentation and
   harnesses.

Reply with the cause and its label, the evidence, and the limits. Diagnosis
makes no production-source edits.

## Establish evidence

Start from the user's exact failure mode, not a nearby error. Prefer a focused,
deterministic signal when one is available: a failing example, captured trace,
targeted script, static comparison, or measured performance baseline. Logs,
traces, static reasoning, and partial evidence can still support a diagnosis
when a complete reproducer is unavailable. Read
[references/feedback-loops.md](references/feedback-loops.md) when a specialized
harness, flaky trigger, bisection, differential comparison, or performance
measurement needs guidance.

Run the signal when possible and record the exact symptom it distinguishes. For
intermittent behavior, seek a useful reproduction rate or compare captured
evidence; report the limitation. For performance regressions, measure a baseline
with a timing harness, profiler, or query plan before changing code.

If no complete loop can be built, do not stop all useful investigation. List
what was tried, gather the available logs, traces, static evidence, or other
partial signals, and limit the diagnosis to what they distinguish. Request a
reproducing environment, captured artifact, or permission for temporary
source instrumentation only when it would change the conclusion. For a
diagnosis-only request, use logs or task-owned scratch probes without changing
production source; if a source edit is necessary and not authorized, state the
limitation or ask for that specific access.

## Test hypotheses

Generate the smallest useful set of ranked, falsifiable hypotheses. Include
alternatives when they guard against anchoring; do not add them to meet a quota.
For each probe, state the prediction it tests and change one variable at a time.

> If <X> is the cause, then changing <Y> makes the bug disappear or changing
> <Z> makes it worse.

If a prediction cannot be stated, sharpen or discard the hypothesis. A
standalone developer may show the ranked list when the user can change its
order. A bounded worker reports consequential uncertainty to its caller.

## Label the cause

Report the confirmed or most-supported cause, its evidence, and the
uncertainty. Label the cause reproduced, inferred from the evidence, or
unresolved. Diagnosis itself does not edit the implementation; an authorized
fix goes through implement. Before you recommend a fix, follow
[fix-root-causes](../principle-fix-root-causes/SKILL.md). Keep the minimized
reproduction: an authorized fix reruns it and decides through the
`testing-code` admission gate whether it becomes a permanent test. If no
correct public seam exists for that test, record it as an architectural
finding rather than exposing an internal seam solely for the test.

## Close out

Report the verification limits and any unresolved blocker. Recommend `/codebase-design`
only when the evidence shows a real architectural testability or coupling
problem; diagnosis does not require a post-mortem or architecture handoff by
default.

> A standalone developer may delegate substantial bounded reads or writes to
> suitable available agents. A bounded worker reports to its caller rather than
> creating an uncontrolled delegation chain.
