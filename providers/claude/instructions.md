## Claude Addendum

- This installation targets Claude Code.
- Install the shared instructions into `~/.claude/CLAUDE.md`.
- Copy skills into `~/.claude/skills/`.
- Provider-specific Claude skills may be installed from `providers/claude/skills/`.
- Keep Claude-specific instructions short and layered on top of the shared
  workflow.
- Auto-approval setup uses Claude `permissions.defaultMode = "auto"`.
- Never add agent attribution to commits or PRs: no `Co-authored-by`,
  `Signed-off-by`, `Generated with`, AI tool signatures, or agent entries in
  contributors lists.
