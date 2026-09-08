---
name: diagnose
description: Disciplined diagnosis loop for hard bugs and performance regressions. Build a feedback loop, reproduce, hypothesize, instrument, fix, and verify. Use when the user says "diagnose this" / "debug this", reports a bug, says something is broken/throwing/failing, or describes a performance regression.
---

# Diagnose

A discipline for hard bugs. Skip phases only when explicitly justified.

When exploring, use the project's own vocabulary (the `docs/agents/CONTEXT.md`
glossary if present) to build a clear mental model, and check `docs/agents/adrs/`
for decisions in the area you're touching. Follow an explicit project or user
override of the `docs/agents/` location.

## Phase 1 — Build a feedback loop

**This is the skill.** Everything else is mechanical. If you have a fast,
deterministic, agent-runnable pass/fail signal for the bug, you will find the
cause — bisection, hypothesis-testing, and instrumentation all just consume that
signal. If you don't have one, no amount of staring at code will save you.

Spend disproportionate effort here.

Ways to construct one — try them in roughly this order:

1. **Failing test / example** at whatever seam reaches the bug — unit, integration, e2e, or a `/testing-code` scratch script.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** (Playwright / Puppeteer) — drives the UI, asserts on DOM/console/network.
5. **Replay a captured trace.** Save a real request / payload / event log to disk; replay it through the code path in isolation.
6. **Throwaway harness.** Spin up a minimal subset of the system (one module, mocked external deps) that exercises the bug with a single call.
7. **Property / fuzz loop.** For "sometimes wrong output", run many random inputs and look for the failure mode.
8. **Bisection harness.** If the bug appeared between two known states (commit, dataset, version), automate "boot at state X, check, repeat" so you can `git bisect run` it.
9. **Differential loop.** Run the same input through old vs new (or two configs) and diff outputs.

Build the right feedback loop and the bug is 90% fixed.

**Iterate on the loop itself.** Make it faster (cache setup, narrow scope),
sharper (assert the specific symptom, not "didn't crash"), and more deterministic
(pin time, seed RNG, isolate filesystem, freeze network). A 2-second
deterministic loop is a debugging superpower; a 30-second flaky one is barely
better than nothing.

**Non-deterministic bugs:** the goal is a higher reproduction rate, not a clean
repro. Loop the trigger, parallelise, add stress, narrow timing windows. A
50%-flake bug is debuggable; 1% is not — raise the rate until it is.

**If you genuinely cannot build a loop**, stop and say so. List what you tried.
Ask for: access to an environment that reproduces it, a captured artifact (HAR,
log dump, core dump, timestamped recording), or permission to add temporary
instrumentation. Do **not** hypothesise without a loop.

## Phase 2 — Reproduce

Run the loop. Watch the bug appear. Confirm:

- [ ] The loop produces the failure mode the **user** described — not a nearby one. Wrong bug = wrong fix.
- [ ] It's reproducible across runs (or at a high enough rate for non-deterministic bugs).
- [ ] You captured the exact symptom (error, wrong output, slow timing) so later phases can verify the fix.

## Phase 3 — Hypothesise

Generate the smallest useful set of ranked, falsifiable hypotheses before
testing. Include alternatives when they guard against anchoring; do not add
hypotheses to meet a quota.

> Format: "If <X> is the cause, then <changing Y> makes the bug disappear / <changing Z> makes it worse."

If you cannot state the prediction, sharpen or discard it. A standalone
developer may show the ranked list to the user when their context could change
the order. A bounded worker reports consequential uncertainty to its caller.

## Phase 4 — Instrument

Each probe maps to a specific prediction. **Change one variable at a time.**

1. **Debugger / REPL** if the env supports it — one breakpoint beats ten logs.
2. **Targeted logs** at the boundaries that distinguish hypotheses.
3. Never "log everything and grep".

**Tag every debug log** with a unique prefix (`[DEBUG-a4f2]`) so cleanup is a
single grep. For performance regressions, logs are usually wrong: establish a
baseline measurement (timing harness, profiler, query plan), then bisect. Measure
first, fix second.

## Phase 5 — Fix + lasting evidence

Before the fix, decide whether the minimized reproduction earns a permanent
regression test using `/testing-code`'s admission gate. If it does, write the
test at a correct seam where it exercises the real bug pattern as it occurs at
the call site, then watch it fail. If it does not, retain proportionate evidence
such as the reproducible diagnostic loop or a behavior-specific check.

**If no correct seam exists, that itself is the finding.** Note it — the
architecture is preventing the bug from being locked down. Flag it for Phase 6.

Apply the fix, re-run the chosen lasting evidence, then re-run the Phase 1 loop
against the original (un-minimised) scenario.

## Phase 6 — Cleanup + post-mortem

- [ ] Original repro no longer reproduces (re-run the Phase 1 loop)
- [ ] The admitted regression test or other chosen evidence passes
- [ ] All `[DEBUG-...]` instrumentation removed (grep the prefix)
- [ ] Throwaway harnesses owned by the task deleted
- [ ] The confirmed cause and evidence are reported with the fix where the next
      debugger can find them

**Then ask: what would have prevented this bug?** If the answer is architectural
(no good test seam, tangled callers, hidden coupling), hand off to
`/improve-codebase-architecture` with the specifics. Make that recommendation
**after** the fix is in — you know more now than when you started.

> A standalone developer may delegate substantial bounded reads or writes to
> suitable available agents. A bounded worker reports to its caller rather
> than creating an uncontrolled delegation chain.
