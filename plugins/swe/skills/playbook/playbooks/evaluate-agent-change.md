# evaluate-agent-change

Applies when: measure how a skill or prompt change affects agent behavior.

1-preregister-criteria: Write each metric and pass threshold before any run. (explain-measurements)
2-freeze-configuration: Record model, effort, CLI version, judge model, and catalog for each arm.
3-blind-the-candidate: Write organic prompts and sanitized fixture names with no evaluation words.
4-blind-the-grader: Hide arm identity, skill names, and router text from any grader.
5-run-all-arms: Run all arms with the same cases and run count.
6-report-with-spread: Report each metric with run count and interval; small-n gates are harm gates only. (explain-measurements)

Reply: each metric with run count, interval, and its pre-registered verdict.
