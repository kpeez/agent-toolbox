# Plan storage

Plans and handoffs live in `<main checkout>/.agents/plans/`, shared by the
repository's worktrees and kept out of Git. Resolve
`plugins/swe/scripts/handoff.py` from the installed SWE plugin, not from the
current skill or repository directory. Run
`python3 <plugin-root>/scripts/handoff.py dir` in the target repository to
create and print the directory. Do not use `.agents/docs/` or a notes vault for
plans.

- A plan is named `<slug>.md`, where the slug is the work's branch name with
  `/` changed to `-`. The [handoff](../skills/handoff/SKILL.md) skill and its hook
  update the same file, so one file follows the branch from plan to merge.
- Plans are local only. Nothing syncs them to a tracker.

The `dir` command creates the plans directory and its ignore file; do not
describe it as a read-only check.
