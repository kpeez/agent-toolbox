# Stacked pull requests

Read this reference only when the user or established task design calls for a
dependent branch chain. Confirm the stack order and base relationships from
current evidence. Each pull request must stand alone for its own diff. Do not
convert ordinary tasks into a stack merely to create a grouping layer. Branch
independent work from trunk.

A stack is a base-branch chain. The root pull request targets trunk. Each
child branch rebases onto its parent's exact tip, and its pull request targets
the parent branch:

- Create a child as a draft: `gh pr create --draft --base <parent-branch>`.
- Retarget a child: `gh pr edit <pr> --base <parent-branch>`.
- Rebase onto trunk before substantial stack work.
- Put a fix on the lowest branch that owns the code, then replay the branches
  above it.
- When a parent merges, move its child onto trunk as step 4 of the
  [ship-stack playbook](../../swe-mode/playbooks/ship-stack.md) says.

Use GitHub (`gh`) and plain git. Do not require Graphite (`gt`) or other stack
tooling. When the repository already uses stack tooling, follow its documented
publication and merge behavior.
