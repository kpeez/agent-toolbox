# Agent scratch

Choose the lifetime of a file when you write it. Each lifetime has one
place and one end.

| Lifetime | Where | Dies when |
| --- | --- | --- |
| session | `~/agent-scratch/_session/<YYYY-MM-DD>-<slug>/` | 14 days after its newest file (swept) |
| branch | `.agents/scratch/<branch-slug>/` (the same folder as `~/agent-scratch/<repo>/<branch-slug>/`) | its PR is merged and the folder is idle 3 days (swept) |
| keep | `~/artifacts/<repo>/<YYYY-MM-DD-slug>/`, or a curated promotion (below) | never |

`<branch-slug>` is the current branch name with `/` replaced by `-`. On a
detached HEAD it is `detached-<short-sha>`.

## Pick the lifetime

- **Branch**: debris of work on a feature branch. Debris is a probe, a test
  log, a screenshot, a PR-body draft, a plan, or a cloned upstream.
- **Session**: debris of work on the default branch (`main` or `master`) or
  outside a repo. Never write `~/agent-scratch/<repo>/main/`: a default
  branch never merges, so a sweep never removes that folder.
- **Keep**: output a human would re-open, compare, or cite after this task,
  when you can record the command, the config, and the git SHA that made it.
  Write it to `~/artifacts/<repo>/<YYYY-MM-DD-slug>/`, one folder per run.
  Curated human material (a page, research, a prompt) goes to its home with
  `agent-scratch keep <path> --to pages|research|prompts --why "<reason>"`.

Nothing enters the keep tier silently. Promote only when the user asks, or
says yes to an end-of-task offer: "worth keeping: X. Keep it?"

Never write loose files directly in `~/agent-scratch/` or in
`~/agent-scratch/<repo>/`. A reviewer or verifier workspace belongs in the
branch folder of the PR's head branch, as `review-<agent>/`. Do not use
`/tmp` or `mktemp -d` for any of this.

## Sweep

`agent-scratch report` shows what a sweep would remove and lists each
violation of these rules. `agent-scratch sweep` deletes per the config. The
`clean-worktrees` playbook runs the sweep for scratch folders.

## The link

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

Git ignores `.agents/scratch`. The sweep keeps a branch folder until its PR merges, so its evidence outlives the worktree.
