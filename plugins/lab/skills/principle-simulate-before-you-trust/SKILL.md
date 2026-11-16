---
name: principle-simulate-before-you-trust
description: "Before you trust a pipeline, an analysis, or a metric on real data, feed it data with a known answer through the exact same code path and confirm the answer comes back."
disable-model-invocation: true
---

# Simulate before you trust

- **Plant a known effect and check recovery.** Generate data with a known
  effect size or known parameters. Run the real pipeline on it. Check the
  bias of the estimate and the coverage of its interval over many draws. A
  95% interval that covers the truth in 80% of draws is wrong.
- **Run null data many times.** Use data that must show no effect. Run the
  full analysis on hundreds of draws. Compare the false-positive rate with the
  nominal alpha. Eklund, Nichols and Knutsson (2016) ran null comparisons
  through standard fMRI software and found cluster-level false-positive rates
  far above the nominal 5%. The software had been trusted for years.
- **For ML, break the signal on purpose.** Shuffled labels must give chance
  performance. Plant a shortcut feature, such as a watermark or a split
  leak, and confirm your checks detect it.
- **Match the real data.** Give the simulation the same sample size, noise,
  missing data, and correlation structure as the real data. A clean
  simulation of a different problem proves nothing.
- **Keep the simulator.** Put the simulator and its expected result in the
  project skill's scripts, so the check reruns after every change. Use
  [research-skill](../research-skill/SKILL.md) for where it lives.
- **Treat failed recovery as a block.** When the known answer does not come
  back, the real result is not reportable. Fix the pipeline, then rerun the
  real data.

You skipped this when a pipeline's first run on real data is its only run,
when no null data ever went through the analysis, when a metric has no
shuffled-label or chance baseline, when the simulation differs in size or
structure from the real data, or when the simulator exists only in a past
session.
