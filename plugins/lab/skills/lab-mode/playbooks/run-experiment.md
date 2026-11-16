# run-experiment

Applies when: one designed comparison, ablation, or eval run.

You own the design and the integrity of the result. Write the rule first. Run it. Report what happened.

Decide before you run. Give the baseline the same tuning as the change. Record a null or negative result as fully as a win. Repeated keep-or-discard runs on one metric go to autoresearch. When the experiment needs a code change, this playbook keeps what the code must show and what the result means.

1-write-the-decision: Write the hypothesis, the metric, and the decision rule that names the result that would change a decision. (write-the-decision-first)
2-check-prior-work: Do a short search for an existing answer. When a source already answers the question, stop and report that answer with its grade. (review-literature)
3-tune-the-baseline: Give the baseline the same data, compute, and tuning effort as the change, and write down each setting. Check the Comparison section. (claim-checklist)
4-pilot-small: Follow the project's procedure skill when one covers the run, and run its known-good check first. Run the smallest job that exercises the full pipeline, read what the model receives and returns, and estimate the cost of the full run. When no skill covers the pipeline, feed it data with a known answer and confirm the answer returns before the full run. (simulate-before-you-trust, claim-checklist)
5-measure-noise-floor: Repeat the baseline across seeds, and record the run count and the spread. Check the Noise section. (claim-checklist)
6-run-with-provenance: Run the full experiment, and link each result to its command, config, commit, and data version. Check the Provenance section. (claim-checklist)
7-analyze: Run steps 3 to 10 of analyze-results on the results. (analyze-results)
8-record-the-result: Record the result against the decision rule, with each deviation from the written plan. Record null and negative results too. Check the Provenance section. (claim-checklist, write-the-decision-first)
9-feed-the-flywheel: Ask whether this run repeated a procedure or drew a user correction. If yes, propose or update a project skill, and name it in the reply. (encode-the-procedure)

Reply: hypothesis, decision rule, result against the rule with run count and spread, grade, artifact paths, deviations from the plan, any project skill proposed or updated.
