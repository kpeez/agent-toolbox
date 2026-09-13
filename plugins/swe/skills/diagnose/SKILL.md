---
name: diagnose
description: Investigate bugs and performance regressions using focused evidence. Use when asked to diagnose, debug, or explain a failure.
---

# Diagnose

Investigate the reported symptom with enough evidence to support the requested
outcome. Diagnosis and repair are separate outcomes: a request to diagnose or
explain does not authorize implementation edits. When repair is authorized,
continue in-scope investigation and correction through relevant verification.

Use the project's vocabulary when it clarifies the diagnosis. Consult a
`docs/agents/CONTEXT.md` glossary or relevant `docs/agents/adrs/` only when they
bear on the behavior or decision under investigation. Follow an explicit
project or user override of the `docs/agents/` location.

## Establish evidence

Start from the user's exact failure mode, not a nearby error. Prefer a focused,
deterministic signal when one is available: a failing example, captured trace,
targeted script, static comparison, or measured performance baseline. Logs,
traces, static reasoning, and partial evidence can still support a diagnosis
when a complete reproducer is unavailable. Read
[references/feedback-loops.md](references/feedback-loops.md) when a specialized
harness, flaky trigger, bisection, or differential comparison needs guidance.

Run the signal when possible and record the exact symptom it distinguishes. For
intermittent behavior, seek a useful reproduction rate or compare captured
evidence; report the limitation. For performance regressions, measure a baseline
with a timing harness, profiler, or query plan before changing code.

If no complete loop can be built, do not stop all useful investigation. List
what was tried, gather the available logs, traces, static evidence, or other
partial signals, and limit the diagnosis to what they distinguish. Request a
reproducing environment, captured artifact, or permission for temporary
instrumentation only when it would change the conclusion.

## Test hypotheses

Generate the smallest useful set of ranked, falsifiable hypotheses. Include
alternatives when they guard against anchoring; do not add them to meet a quota.
For each probe, state the prediction it tests and change one variable at a time.

> If <X> is the cause, then changing <Y> makes the bug disappear or changing
> <Z> makes it worse.

If a prediction cannot be stated, sharpen or discard the hypothesis. A
standalone developer may show the ranked list when the user can change its
order. A bounded worker reports consequential uncertainty to its caller.

## Diagnose or repair

For a diagnosis-only or explanation request, report the confirmed or
most-supported cause, evidence, and uncertainty. Do not edit the implementation.

For an authorized repair, decide whether the minimized reproduction earns a
permanent regression test using `/testing-code`'s admission gate. If it does,
write it at a correct public seam and watch it fail before applying the fix. If
it does not, retain proportionate evidence such as the diagnostic loop or a
behavior-specific check. If no correct seam exists, record that as an
architectural finding rather than exposing an internal seam solely for the test.

Apply the authorized fix, rerun the chosen evidence against the original
scenario, and run relevant checks. A failing required check blocks completion or
publication, but continue in-scope diagnosis and correction when that can
resolve it. Report unrelated baseline failures without silently fixing unrelated
code.

## Close out

Remove task-owned temporary instrumentation and harnesses. Report the confirmed
cause, evidence, verification limits, and any unresolved blocker. Recommend
`/improve-codebase-architecture` only when the evidence shows a real
architectural testability or coupling problem; diagnosis does not require a
post-mortem or architecture handoff by default.

> A standalone developer may delegate substantial bounded reads or writes to
> suitable available agents. A bounded worker reports to its caller rather than
> creating an uncontrolled delegation chain.
