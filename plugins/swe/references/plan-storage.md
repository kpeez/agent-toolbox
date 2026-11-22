# Plan storage

A plan is one HTML file. Copy [plan-template.html](plan-template.html) and
fill it in: the title, the goal, the plan sections, and one decision block for
each open decision. Each decision has an id (`d1`, `d2`), its options, and one
recommended option. Keep the inline CSS and JS. Add no external asset and no
network call.

The plan lives at `.agents/scratch/<branch-slug>/<slug>.plan.html`, always.
`<slug>` names the work. `<branch-slug>` is the branch name with `/` changed
to `-`. [Agent scratch](agent-scratch.md) defines the folder and its link.
Plans do not go to the vault.

Show the page to the user the way the user's own instructions say to show an
HTML file. When no instruction says how, give the file path.

Settle the decisions one of two ways:

- Interview the user in chat, with the
  [interview-user](../skills/interview-user/SKILL.md) skill.
- The user taps answers on the page and pastes the copy block back. The block
  has one line for each decision:

  ```
  d1: Option text | note: the user's note
  d2: (no answer)
  ```

A note with no option picked reads `d2: (no answer) | note: <text>`.

Treat a pasted block as the user's answers. Ask about each `(no answer)` line,
or take your recommended option and say so.

- Plans are local only. Nothing syncs them to a tracker.
- Delete a plan when its pull request merges. The pull request and the code
  are the record.

Handoffs are not files. The [handoff](../skills/handoff/SKILL.md) skill writes
the work's current state to its tracker issue, or to a pull request comment
when the project has no tracker. The
[log-decisions](../skills/log-decisions/SKILL.md) skill keeps the decision log
at `.agents/scratch/<branch-slug>/decisions.jsonl` during the run.
