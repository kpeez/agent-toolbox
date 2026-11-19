# Plan storage

A plan is an HTML source file. It lives at
`.agents/docs/plans/<slug>.plan.src.html` when the project has a
`.agents/docs` folder. Otherwise it lives in `.agents/scratch/<branch-slug>/`.
The slug is the work's branch name with `/` changed to `-`.
[Agent scratch](agent-scratch.md) defines the scratch folder and its link.
The HTML plan workflow owns the plan's format.

- Plans are local only. Nothing syncs them to a tracker.
- Delete a plan when its pull request merges. The pull request and the code
  are the record.

Handoffs are not files. The [handoff](../skills/handoff/SKILL.md) skill writes
the work's current state to its tracker issue, or to the pull request body
when the project has no tracker. The
[log-decisions](../skills/log-decisions/SKILL.md) skill keeps the decision log
at `.agents/scratch/<branch-slug>/decisions.jsonl` during the run.
