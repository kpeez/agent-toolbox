---
name: principle-explain-measurements
description: "Before you trust, report, or act on a measured number, such as a speedup, latency, or eval result: name what limits it, and record its run count and spread."
user-invocable: false
---

# Explain measurements

- **Name the limiter**: the resource or code path that bounds the result, such
  as a core, a lock, the disk, the network, or the load generator. Get it from
  a profile or from system counters taken during the run, and map it to the
  source. A guess from reading the code is not a limiter. Ask why the number
  is not twice as good; if you cannot answer, you do not know what you
  measured.
- **Rule out other causes**: errors, skipped or cached work, code that never
  ran, a side left on default settings, noise, and a part too small to matter
  end to end. Rule out each one with evidence.
- **Record the run count and the spread** (range or interval) with the number,
  in the report or a linked artifact. One run has no spread.
- For an eval result, also check that every run did the task and that the gap
  holds across runs.

Signs that you skipped this: a number with no run count, no spread, or no
named limiter; or a time saving larger than the total time of the changed
part.
