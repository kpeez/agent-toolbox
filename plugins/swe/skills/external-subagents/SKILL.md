---
name: external-subagents
description: "Delegate bounded work when the caller explicitly requests OpenCode, GitHub Copilot, or another non-host provider. Use direct ACP/MCP session controls for OpenCode when configured, or a local CLI for individual assignments."
---

# External subagents

Prefer host-native subagents unless an external provider is explicitly
authorized. Before sending private repository content, require provider-specific
explicit authorization.

For parallel or ongoing OpenCode work, use the direct ACP bridge when its MCP
tools are configured. Read [the bridge guide](references/opencode-acp.md) for
session controls, permission configuration, and limits. Call those tools
directly; do not add a host-agent forwarding layer. Bridge agent IDs belong to
the bridge, not the host's native subagent tools. Use the CLI below for an
individual assignment when the bridge is unavailable.

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
