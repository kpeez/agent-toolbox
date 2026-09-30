# Plan storage and sync

Plans live in `<main checkout>/.agents/plans/`, shared by the repository's
worktrees and kept out of Git. Resolve `plugins/swe/scripts/plan_sync.py` from
the installed SWE plugin, not from the current skill or repository directory.
Run `python3 <plugin-root>/scripts/plan_sync.py dir` in the target repository to
create and print the directory. Do not use `.agents/docs/` or a notes vault for
plans.

- A file named `ABC-123-short-slug.md` is eligible to mirror to a document on
  Linear issue `ABC-123`. A configured host Stop hook attempts to sync changed
  plans after a turn; hook delivery varies by host. Explicitly run
  `python3 <plugin-root>/scripts/plan_sync.py sync ABC-123-short-slug.md` to
  push a changed plan, then inspect its result and `status`. Verify the remote
  document separately when actual delivery must be established.
- An unkeyed plan, including one linked from a GitHub issue, stays local. Link
  its path or content through the GitHub workflow the user authorized; a
  GitHub issue number does not activate the Linear mirror.

The `dir` command creates the plans directory and its ignore file. `status`
can also create the ignore file; do not describe either command as a pure
read-only check. A status of `in sync` reports the script's recorded local
state, not an independently observed host-hook run or remote read. If the Linear document was
edited separately, sync skips overwriting it. Resolve the difference before
using `sync --force`; force overwrites the remote document.
