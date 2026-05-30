---
name: delegating-work
description: Offload token-heavy work to cheaper workers to preserve the orchestrator's tokens and context — explore codebases with a local model, and delegate code generation to external agentic CLIs (codex / antigravity / copilot). Use before reading many files to answer a question, or before writing a substantial, well-specified chunk of code a worker can draft and you review.
---

# Delegating work to cheaper workers

Keep your own (expensive) context lean by handing token-heavy work to cheaper workers,
then reviewing what comes back. Two tools, opposite jobs.

Both are CLIs you run via Bash from the repo root. The worker does the file reading and
generation itself, so that bulk never enters your context — you act on its returned answer
(and review it). Commands assume `~/.agents/bin` is on PATH; if a command is "not found",
use the guaranteed path `python3 ~/.agents/skills/delegating-work/scripts/<script>.py`.

## local-explore — codebase exploration (local, free, read-only)

Gathers files and asks a local ollama model to answer a question about them, so you never
load the raw files into your own context. Reach for it to answer "how does X work / where
is Y / summarize this area" across more than a couple of files.

```
local-explore "How does auth work?" src/ lib/auth.py
local-explore --dry-run "..." src/            # preview files + token count, no model call
```

- Compressive and low-stakes — a slightly imperfect summary is fine because you review it.
  Scope paths tightly; latency scales with how much you feed in (tens of seconds to a
  couple of minutes on this machine), and it runs serially.
- Read-only and localhost-only → safe to run without gating.
- Needs `ollama serve`. Default model `gpt-oss:20b`; pass `--model qwen3.5:9b` to switch.
- **Don't** use it for a single-file lookup you'd read faster yourself, or where an
  imperfect summary would mislead you.

## ext-subagent — code generation (external, smart, write-capable)

Delegates a coding task to an external agentic CLI that is near-Opus smart and billed
separately from your tokens. Prefer this over a local coder for real code generation.

```
ext-subagent codex   "Implement X following existing patterns. Run the tests." --model gpt-5.4-mini
ext-subagent copilot --prompt-file task.md --model claude-sonnet-4.6
echo "Refactor the auth module to use DI; preserve tests." | ext-subagent antigravity -
```

- Provider → engine: `codex` → GPT-5.x, `antigravity` → Gemini, `copilot` → Sonnet.
- For long or code-heavy prompts, write the prompt to a file and pass `--prompt-file`
  (or pipe stdin) so you never have to shell-escape it.
- `--retries N` retries failures with backoff — only for read/answer tasks, **never** for
  file-writing tasks (re-running is not idempotent). `--max-output-chars N` caps the reply.
- `antigravity` has no per-call `--model` (set it in `~/.gemini/antigravity-cli/settings.json`
  or via `agy /model`); passing `--model` to it errors.
- Workers launched through `ext-subagent` get `AGENTSPEC_INVOKED_SUBAGENT=1` and
  an explicit prompt instruction to do the assigned task directly instead of
  invoking subagents or delegation tools. If a worker still tries to run
  `ext-subagent`, the inherited environment guard refuses the nested call.
- Writes files with auto-approve. `codex` is sandboxed to the workspace; `antigravity` and
  `copilot` are not — review their changes with `git diff` before trusting them.

## Delegate vs. do it yourself

Delegate substantial, well-specified codegen where a worker drafts and you review. Write it
yourself when the logic is subtle enough that reviewing someone else's code would cost more
than writing it. For exploration, delegate whenever the answer needs more than a couple of
files in context.
