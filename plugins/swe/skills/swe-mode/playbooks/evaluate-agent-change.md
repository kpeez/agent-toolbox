# evaluate-agent-change

Applies when: measure how a skill or prompt change affects agent behavior.

You own the experiment design. Plan, blind, run, synthesize.

Blinding rules hold for every run. No directory, file, or prompt the candidate sees contains `eval`, `test`, `judge`, `experiment`, `rubric`, `score`, `compare`, `benchmark`, or `candidate`. The candidate prompt reads as an organic user request that states the goal, not the meta. Do not ask a candidate to list the skills, principles, or files it applied. Ask for design notes in general. Do not tell a candidate that other candidates exist. The judge may know it judges but sees outputs only by sanitized label, never by model name. When two variants are compared, one judge scores both sets in one pass on one scale.

1-frame-variant: State the variant under test and the behavior that counts as success. Write a rubric of 3 to 6 concrete criteria for the judge only.
2-preregister-criteria: Write each metric and pass threshold before any run. (explain-the-number)
3-freeze-configuration: Record model, effort, CLI version, judge model, and catalog for each arm.
4-sanitize-environments: Give each candidate its own working directory with project-shaped names, the variant in place, and the context an organic task would have.
5-blind-the-candidate: Write one organic prompt with no evaluation words and send the same prompt to each candidate.
6-run-all-arms: Run all arms in parallel with the same cases and run count, each in its own directory. (swarm)
7-blind-the-judge: Run one judge on a different model with the rubric and sanitized labels only. Hide arm identity, skill names, and router text. (swarm)
8-verify-chain-from-transcripts: Grade chain-following from the files each candidate opened in its own transcript and from code shape, never from self-report. Claude Code keeps them in `~/.claude/projects/<project-slug>/*.jsonl` and Codex in `~/.codex/sessions/`. Never read transcripts of unrelated projects.
9-read-every-output: Read each output end to end and compare it to the judge's verdict. Disagreement means a biased model or an ambiguous rubric.
10-report-with-spread: Report each metric with run count and interval. Small-n gates are harm gates only. (explain-the-number)

Reply: the variant, the rubric, per-candidate notes, the judge's verdict, each metric with run count, interval, and pre-registered verdict, your synthesis, and whether to promote the variant.
