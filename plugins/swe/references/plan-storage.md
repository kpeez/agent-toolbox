# Plan storage

A plan is an HTML source file. It lives at
`.agents/docs/plans/<slug>.plan.src.html` when the project has a
`.agents/docs` folder. Otherwise it lives in `.agents/scratch/<branch-slug>/`.
The slug is the work's branch name with `/` changed to `-`.
[Agent scratch](agent-scratch.md) defines the scratch folder and its link.
The HTML plan workflow owns the plan's format.

A packed page, `<slug>.plan.html`, sits next to its source.

- A plan in `.agents/docs/plans/` is the lasting statement of the work's
  intent. Keep it after the pull request merges. `.agents/docs` is the
  project's folder in the notes vault, and the vault decides how it stores
  the packed page.
- A plan in `.agents/scratch/<branch-slug>/` is local only. Delete it when
  its pull request merges.
- When the user signs off on a plan, link the plan's path on the tracker
  issue.

Handoffs are not files. The [handoff](../skills/handoff/SKILL.md) skill writes
the work's current state to its tracker issue, or to a pull request comment
when the project has no tracker. The
[log-decisions](../skills/log-decisions/SKILL.md) skill keeps the decision log
at `.agents/scratch/<branch-slug>/decisions.jsonl` during the run.
