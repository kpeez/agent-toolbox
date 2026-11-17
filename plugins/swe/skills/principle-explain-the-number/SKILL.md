---
name: principle-explain-the-number
description: "Before you measure, and before you trust, report, or act on a number you measured, such as a speedup, a regression, a throughput, a latency, or an eval result, find what limits it and rule out that it measured something else."
disable-model-invocation: true
---

# Explain the number

- **Write the decision before you run.** Name the result that would change it,
  and the noise floor. Stop when the run-to-run spread is larger than the
  effect.
- **Ask "why not double?"** Name the resource or code path that bounds the
  result. Get it from a profile or from counters taken during a run. A guess
  from reading the code is not a limiter.
- **List what else the number could measure.** Examples are errors, skipped or
  cached work, code that never ran, an untuned side, noise, and a part too
  small to matter. Rule out each one with evidence.
- **Keep the run count, the spread, and the limiter with the number.**

For a performance number, run the `benchmark-checklist` skill. For an eval
result, ask three questions. Did every run do the task? Does the gap hold
across trials and models? Does the scenario matter?
