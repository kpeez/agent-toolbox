# Stacked pull requests

Read this reference only when the user or established task design calls for a
dependent branch chain. Stack only when changes depend on each other, and keep
stacks shallow. Branch independent work from trunk. Confirm the stack order and
base relationships from current evidence. Each pull request must stand alone for
its own diff.

Rebase onto trunk before substantial stack work. Put a fix on the lowest branch
that owns the code, then replay the branches above it.

## Publish and land with `gh stack`

Use `gh stack` whenever it is available in the repository (`gh-stack` exists in
the git common directory or `gh stack` succeeds).

1. **Publish.** Keep subagents committing in their own worktrees without pushing
   or opening pull requests. The coordinator rebases the unpushed branches into
   one line, verifies the top branch, and runs one `gh stack link` command from
   bottom to top (or `gh stack submit --auto` when the stack is already tracked
   locally). Do not hand-chain `gh pr create --base <parent-branch>` in a
   `gh-stack` repository.
2. **Replace auto-generated PR bodies.** `gh stack` writes its own titles and
   bodies. After `gh stack link`, render each body with `scripts/pr_body.ts render`,
   update each pull request, and check the published body:

   ```bash
   gh pr edit <n> --title "<title>" --body-file <rendered>
   gh pr view <n> --json body --jq .body | sh <ship-pr>/../../scripts/run-ts <ship-pr>/scripts/pr_body.ts check -
   ```

3. **Land a fully verified stack.** `gh stack merge` is all-or-nothing and
   refuses draft pull requests. When every pull request in the stack holds a
   valid independent verdict, mark each one ready with `gh pr ready <n>`, land
   the stack with `gh stack merge <stack> --yes --squash` (or the repository's
   merge method), confirm each pull request state with `gh pr view`, and delete
   the merged remote branches yourself afterward.
4. **Land a partial run.** When only a bottom prefix of the stack is verified,
   land one pull request at a time from the bottom as step 4 of
   [ship-stack](../../swe-mode/playbooks/ship-stack.md) describes.

## Fallback without `gh stack`

When `gh stack` is unavailable on the host or repository, fall back to plain
`gh` and git:

- Create a child as a draft: `gh pr create --draft --base <parent-branch>`.
- Retarget a child: `gh pr edit <pr> --base <parent-branch>`.
- When a parent merges, move its child onto trunk as step 4 of the
  [ship-stack playbook](../../swe-mode/playbooks/ship-stack.md) says.

In a repository with a `gh-stack` file in the git common directory, the swe
hook blocks a non-trunk `--base` even when the host lacks the extension.
There, install it with `gh extension install github/gh-stack` instead of
falling back.
