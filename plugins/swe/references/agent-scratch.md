# Agent scratch

Scratch is for debris: a probe, a test log, a screenshot, a PR-body draft, a
plan, a cloned upstream. It lives inside the git worktree and dies with it.

## Where scratch goes

- **In a worktree**: `.agents/scratch/` at the worktree top level. It is a real
  folder, never a link, and Git ignores it. Group files in
  `.agents/scratch/<branch-slug>/`, where `<branch-slug>` is the branch name
  with `/` replaced by `-` (`detached-<short-sha>` on a detached HEAD).
  `wt remove` deletes the worktree and the scratch with it.
- **Outside a worktree** (the main checkout, or no repo): use the harness
  scratchpad folder. With none, make a folder with `mktemp -d`. Write no
  `.agents/scratch/` in the main checkout.
- **A reviewer or verifier** makes its own worktree
  (`wt switch --create <branch>`) or uses the scratchpad. It never clones the
  repo by hand into `~/agent-scratch/`.

Use `wt` for worktrees, never `git worktree`.

## Record

When a human would re-open, compare, or cite the output after the task, write
it to `~/artifacts/<repo>/<YYYY-MM-DD-slug>/`, one folder per run. Outside a
repo, use `~/artifacts/_misc/<YYYY-MM-DD-slug>/`. Put one line in the folder
that says what made it: the command, the git SHA, or the session.

## Library

`~/Documents/_ai/pages/`, `~/Documents/_ai/research/`, and
`~/Documents/_ai/prompts/` hold what the user chooses to promote. Write there
only when the user asks.

## Make the folder

A new worktree has no `.agents/scratch/`. Run this from the worktree top
level. It is safe to run again. It makes a real folder and replaces a link
that an old setup left (old setups linked `.agents/scratch` to
`~/agent-scratch/<repo>`):

```sh
sh -c '[ -L .agents/scratch ] && rm .agents/scratch
mkdir -p .agents/scratch
exclude="$(git rev-parse --git-common-dir)/info/exclude"
grep -qxF /.agents/scratch "$exclude" 2>/dev/null || echo /.agents/scratch >> "$exclude"'
```

`rm` on a link removes the link only, not the folder it pointed to.

Old `~/agent-scratch/<repo>/` folders hold scratch from before this rule.
Nothing sweeps them. Review each by hand, move what is worth keeping to
`~/artifacts/`, and delete the rest.
