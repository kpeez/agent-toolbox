# analyze-results

Applies when: results or logs that exist and need a conclusion.

You own the conclusion and its grade. Check the data first. Then conclude.

Raw results come before summaries. A new analysis is exploratory unless a written plan names it. Do not run new experiments here. When the data cannot decide, say so and name the next experiment. A designed run goes to run-experiment. A source from others goes to appraise-source.

1-locate-raw-results: Find the logs, predictions, and configs, and link each number you will report to its raw file. Check the Provenance section. (claim-checklist)
2-state-the-decision: Write the decision this analysis feeds. Follow the written plan when one exists. Label each new analysis exploratory. (write-the-decision-first)
3-check-the-run-ran: Check for errors, skipped items, crashed seeds, and truncated outputs, and confirm that item counts match the dataset. Follow the project's procedure skill when one covers the run. Check the Raw data section. (claim-checklist)
4-check-the-pipeline: When a project skill with a known-good run covers the pipeline, run that check. When none does and no simulation ran, feed the pipeline data with a known answer and confirm the answer returns. (simulate-before-you-trust)
5-measure-noise: For each number, record the run count and the spread, and compare each gap to the noise floor. Check the Noise section. (claim-checklist)
6-check-comparison: For each "A beats B" result, confirm that both sides got the same data, compute, and tuning. Check the Comparison section. (claim-checklist)
7-read-examples: Read raw inputs and outputs from both sides of each aggregate, including failures. Check the Raw data section. (claim-checklist)
8-rule-out-rivals: List the other explanations, such as leakage, contamination, a metric artifact, or a confound, and mark each as ruled out or open. Check the Rivals section. (claim-checklist)
9-make-figures: Make one figure or table for each result you report, with its spread shown. (making-plots)
10-grade-the-conclusion: Give the conclusion one grade, and state the claim at the scope the evidence supports. (grade-the-evidence)
11-feed-the-flywheel: Ask whether this run repeated a procedure or drew a user correction. If yes, propose or update a project skill, and name it in the reply. Record a proposed skill in the "Procedure skills" list of `research-context`, marked proposed. (encode-the-procedure)

Reply: the conclusion with its grade, numbers with run count and spread, rivals ruled out and still open, figure paths, the next experiment, and any project skill proposed or updated.
