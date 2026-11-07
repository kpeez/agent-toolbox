# Agent scratch

Agent debris goes in `.agents/scratch/<branch-slug>/`, one folder per
branch. Debris is a probe, a test log, a screenshot, a PR-body draft, or a
cloned upstream. `<branch-slug>` is the current branch name with `/` replaced
by `-`. On a detached HEAD it is `detached-<short-sha>`.

Write to `artifacts/` only when both are true:

- A human would re-open, compare, or cite the file after this task.
- You can record the command, the config, and the git SHA that produced it.

Everything else goes in scratch. Do not use `/tmp` or `mktemp -d` for it.

`.agents/scratch` is a link to `~/agent-scratch/<repo>/`, where `<repo>` is
the folder name of the main checkout. The llmos plugin makes the link only at
session start, only in the session's own folder, and only for a repo with a
vault project. A worktree made later in the session usually has no link. Run this from the worktree top level. It is
safe to run again:

```sh
sh -c 'repo=$(basename "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")")
mkdir -p ~/agent-scratch/"$repo" .agents
[ -e .agents/scratch ] || ln -s ~/agent-scratch/"$repo" .agents/scratch
exclude="$(git rev-parse --git-common-dir)/info/exclude"
grep -qxF /.agents/scratch "$exclude" 2>/dev/null || echo /.agents/scratch >> "$exclude"'
```

Git ignores `.agents/scratch`. Keep your scratch folder until the branch
merges, so its evidence outlives the worktree. The `clean-worktrees` playbook
removes the folders of merged branches.
