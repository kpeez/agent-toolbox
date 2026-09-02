---
name: external-subagents
description: "Delegate one bounded assignment through a local external-provider CLI when the caller explicitly requests OpenCode, GitHub Copilot, or another non-host provider."
---

# External subagents

Prefer host-native subagents. Use direct local CLI delegation to an external
provider such as OpenCode or GitHub Copilot only when that provider is
explicitly authorized. Before sending private repository content, require
provider-specific explicit authorization.

Give the provider exactly one bounded assignment and the absolute worktree
path. Host sandbox and approval policy still apply, and the external CLI has
its own tool, path, and URL permissions. Inspect its installed help/config,
then choose only scoped permissions the user approved; never auto-select broad
bypass permissions. Prompt wording alone does not enforce read-only behavior,
and a deny-write flag does not prevent shell commands from writing. Do not
silently change providers or retry with broader scope.

```sh
opencode run --dir /abs/worktree "..."
copilot -C /abs/worktree -p "..." <authorized-permission-flags>
```
