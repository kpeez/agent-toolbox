---
name: principle-explain-the-number
description: "Before you trust, report, or act on a number you measured, such as a speedup, a regression, a throughput, a latency, or an eval result, find what limits it and rule out that it measured something else."
disable-model-invocation: true
---

# Explain the number

- **Ask "why not double?"** Name the resource or code path that bounds the
  result, such as a core, a lock, the disk, the network, or the load generator
  itself. Get it from a profile or from system counters taken during a run,
  then map it to the source. A guess from reading the code is not a limiter.
  If you cannot say why the number is not twice as good, you do not know what
  you measured.
- **List what else the number could measure, and rule out each one with
  evidence.** The usual suspects are errors, skipped or cached work, code that
  never ran, an untuned side (one left on default settings), noise, and a
  part too small to matter end to end.
- **Keep the evidence with the number.** Put the run count, the spread (a
  range or an interval), and the limiter in the notes or a linked artifact.
  One run has no spread.

For a performance number, run the full procedure with the
`benchmark-checklist` skill. For an eval result, ask the same of the trials.
Did every run do the task? Does the gap hold across trials and models? Does
the scenario matter?

You skipped this when the evidence behind a number has no run count, no
spread, or no named limiter, or when the time saved is larger than the time
the changed part took.

Distinct from [prove-it-works](../principle-prove-it-works/SKILL.md), which checks that an output is real.
