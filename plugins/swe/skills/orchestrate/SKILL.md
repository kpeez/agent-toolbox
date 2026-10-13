---
name: orchestrate
description: Split work across subagents and integrate results, or delegate to an external provider the user named (OpenCode, Copilot). Use for parallel tasks, investigations, or reviewers. Not for a single edit or one direct review.
---

# Orchestrate

Keep requirements, decisions, synthesis, and final acceptance with the lead.
Use the host's available delegation facilities and configured roles, choosing
the smallest capable agent. Delegation does not expand the user's scope or
authority and does not require a plan or tracker. This skill's job is bounded
coordination plus independent review.

Choose work that can proceed independently and gives each worker a complete
result to deliver. Keep tightly coupled changes with one agent. Do not split
work merely to increase the agent count. When one deterministic script can
make every edit, run it yourself instead of fanning out hand edits.

Before dispatch, apply the [delegation preflight](references/delegation-contract.md):
check the effective model, provider, role, tools, write scope, and host
capability against current user and project constraints. Do not infer these
from a role name or silently fall back when a permitted route is unavailable.

## Assign bounded work

Give each worker a brief with these fields. A field you cannot fill means the
work is not scoped yet. For a one-command task, one paragraph that names the
goal, scope, verify, and report fields is enough.

- **Goal**: the outcome in one sentence that a worker with no chat access can
  act on.
- **Scope**: the paths it may write, the paths it may not, and its worktree or
  branch.
- **Context**: requirements, source links, and useful paths. Paste source text
  and upstream reports that the worker cannot access.
- **Acceptance**: checkable criteria, one per line.
- **Verify**: the exact commands and known gotchas.
- **Timebox**: a rough cap. At the cap, the worker returns partial findings
  and stops.
- **Forbidden**: actions outside its authority, such as fixes outside scope or
  a force-push.
- **Report**: status, changed paths or artifacts, the commands it ran,
  evidence, deviations, and unresolved concerns.

Delegate independent work in parallel only with isolated worktrees or disjoint
write ownership. When two workers would write the same state, follow
[separate-shared-state](../principle-separate-shared-state/SKILL.md). Tell
workers they are not alone and must preserve others' changes. Ask for stable
paths and focused evidence, not bulk logs.

## External providers

Use host-native subagents. Use an external provider such as OpenCode or GitHub
Copilot only when the user named it. Before you send private repository
content to it, require explicit authorization for that provider.

Apply the delegation preflight before launch. If a model constraint applies,
set a permitted provider model explicitly. Report an unavailable model or
permission; do not switch routes silently.

For parallel or ongoing OpenCode work, use the direct ACP bridge when its MCP
tools are configured. Read [the bridge guide](references/opencode-acp.md) for
session controls, permission configuration, and limits. Call those tools
directly; do not add a host-agent forwarding layer. Bridge agent IDs belong to
the bridge, not the host's native subagent tools. Use the CLI for an individual
assignment when the bridge is unavailable.

Give the provider exactly one bounded assignment and the absolute worktree
path. The host sandbox and approval policy still apply, and the external CLI
has its own tool, path, and URL permissions. Inspect its installed help and
config, then scope permissions to the approved assignment. Choose an automatic
permission mode only after you confirm that its actual grants fit that scope.
Prompt wording does not enforce read-only behavior, and a deny-write flag does
not stop shell commands from writing. Do not change providers silently or retry
with broader scope.

## Integrate and follow up

Inspect worker results, resolve interactions, and verify the assembled outcome.
A worker report is an input, not final verification. For substantive changes,
use a reviewer who did not implement them; ask for concrete correctness,
requirement, verification, and unnecessary-complexity findings. Fix supported
findings and re-review when the changed risk warrants it.

Give a fix round, follow-up, or retry to a fresh subagent with consolidated
scope: the original brief, every later directive, and the prior report and
branch. Resume an earlier agent only when the work needs state that lives in
it, such as uncommitted changes or a running process.

For one direct PR or diff review, give the reviewer the exact target and
criteria directly; orchestration is useful when coordination itself adds value.

Continue while evidence supports a useful in-scope next step. Diagnose repeated
failure before redispatching and stop loops that produce no new evidence.
Workers return consequential decisions and blockers to their caller. The lead
asks the user when progress requires a material scope or preference decision,
missing authority or capability, destructive action, or resolution of
contradictory requirements.
