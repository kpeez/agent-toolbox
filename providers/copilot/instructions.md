## Copilot Addendum

- This installation targets GitHub Copilot CLI.
- Install the shared instructions into `~/.copilot/copilot-instructions.md`.
- Store canonical skills in `~/.agents/skills/`; Copilot reads this personal
  skills directory directly.
- Keep Copilot-specific instructions short and layered on top of the shared
  workflow.
- Auto-approval setup installs `~/.copilot/bin/copilot-auto`, which uses
  native `--allow-all` plus destructive `--deny-tool` rules.
- Never add agent attribution to commits or PRs: no `Co-authored-by`,
  `Signed-off-by`, `Generated with`, AI tool signatures, or agent entries in
  contributors lists.
