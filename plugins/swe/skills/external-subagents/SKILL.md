---
name: external-subagents
description: Delegate bounded work to an explicitly requested external provider such as OpenCode or GitHub Copilot.
---

# External subagents

Prefer host-native subagents unless an external provider is explicitly
authorized. Before sending private repository content, require provider-specific
explicit authorization.

Use the shared [delegation preflight](references/delegation-contract.md) before
launch. If a model constraint applies, resolve and explicitly set a permitted
provider model; do not inherit an unverified default. Report unavailable models
or permissions instead of switching routes silently.

For parallel or ongoing OpenCode work, use the direct ACP bridge when its MCP
tools are configured. Read [the bridge guide](references/opencode-acp.md) for
session controls, permission configuration, and limits. Call those tools
directly; do not add a host-agent forwarding layer. Bridge agent IDs belong to
the bridge, not the host's native subagent tools. Use the CLI for an individual
assignment when the bridge is unavailable.

Give the provider exactly one bounded assignment and the absolute worktree
path. Host sandbox and approval policy still apply, and the external CLI has
its own tool, path, and URL permissions. Inspect its installed help/config,
then scope permissions to the approved assignment. Choose any automatic
permission mode only after confirming that its actual grants fit that scope.
Prompt wording alone does not enforce read-only behavior, and a deny-write flag
does not prevent shell commands from writing. Do not silently change providers
or retry with broader scope.
