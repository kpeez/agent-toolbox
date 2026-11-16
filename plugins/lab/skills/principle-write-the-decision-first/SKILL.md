---
name: principle-write-the-decision-first
description: "Before an experiment or analysis runs, write the hypothesis, metric, comparison, decision threshold, analysis plan, and stopping rule to a file, before the first result."
disable-model-invocation: true
---

# Write the decision first

- **Write the plan to a file before the first result exists.** Put in it the
  hypothesis, the metric, the comparison, the analysis plan, and the stopping
  rule. Commit the file or note its hash, so the time of writing is checkable.
- **Name the result that would change a decision.** Write the decision, and the
  threshold on the metric that flips it. State what you will do if the result
  is null.
- **Fix the analysis plan.** Write the data split, the seeds, the aggregation
  (mean, median, or worst case), and the exclusion rules. Write the number of
  runs per arm.
- **Fix the stopping rule.** Write the budget or the condition that ends the
  run. Do not stop early because a result looks good.
- **Label each later analysis choice.** After results exist, tag every new
  choice as a deviation from the plan, with its reason, or as exploratory. Only
  planned analyses are confirmatory. Report exploratory results as leads that
  need their own test. This limits the garden of forking paths (Gelman and
  Loken): many defensible analysis choices, picked after the data, inflate
  the false-positive rate.

You skipped this when analysis choices come after the results with no label,
when the metric or the exclusion rule changed after a run, when the plan file
is newer than the first result, or when no result could have changed the
decision.

For a loop of runs, the approved program in
[autoresearch](../autoresearch/SKILL.md) is the written decision. Size the
noise per [claim checklist: noise](../lab-mode/references/claim-checklist.md#noise).
