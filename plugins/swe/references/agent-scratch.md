# Agent scratch

Agent debris goes in `.agents/scratch/<branch-slug>/`. Debris is a probe, a
test log, a screenshot, a PR-body draft, or a cloned upstream. `<branch-slug>`
is the current branch name with `/` replaced by `-`.

Write to `artifacts/` only when both are true:

- A human would re-open, compare, or cite the file after this task.
- You can record the command, the config, and the git SHA that produced it.

Everything else goes in scratch. Do not use `/tmp` or `mktemp -d` for it.

`.agents/scratch` is a link to `~/agent-scratch/<repo>`. The llmos plugin makes
it at session start. When the link is missing, make it:

```sh
mkdir -p ~/agent-scratch/<repo>
ln -s ~/agent-scratch/<repo> .agents/scratch
```

Git ignores `.agents/scratch`. Keep your scratch folder until the branch
merges, so its evidence outlives the worktree. The `clean-worktrees` playbook
removes the folders of merged branches.
