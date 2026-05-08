## Codex Addendum

- This installation targets Codex CLI.
- Install the shared instructions into `~/.codex/AGENTS.md`.
- Store canonical skills in `~/.agents/skills/`.
- Mirror skills into `~/.codex/skills/` for Codex CLI reliability.
- Copy skills rather than symlinking them.
- Auto-approval setup uses native `approval_policy = "on-request"` with
  `sandbox_mode = "workspace-write"` and a compact Codex `.rules` file for
  destructive shell prompts.
- Never add agent attribution to commits or PRs: no `Co-authored-by`,
  `Signed-off-by`, `Generated with`, AI tool signatures, or agent entries in
  contributors lists.
