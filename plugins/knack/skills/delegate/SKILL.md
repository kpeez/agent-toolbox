---
name: delegate
description: Delegate token-heavy work to cheaper workers instead of doing it yourself — route reads/exploration to a fast model and code generation to a medium model, then review what comes back. Use whenever you are about to read many files to answer a question, or write a substantial, well-specified chunk of code — including from within /orchestrate, /implement, /tdd, /blueprint, /diagnose, and /improve-codebase-architecture.
user-invocable: false
---

# Delegate work to cheaper workers

**You are the lead agent — delegate; don't do it all yourself.** Plan, delegate,
and review; don't burn your own context reading bulk files or typing
implementation. Keep your context lean: hand token-heavy work to a cheaper
worker, act on the answer it returns, and review every write with `git diff`.
You decide; you never write the bulk yourself.

## Role tiers

Pick the least powerful model that fits, by role:

| Role       | Use for                                                              | Codex                | Claude |
| ---------- | ------------------------------------------------------------------- | -------------------- | ------ |
| **fast**   | reads / explore / summarize across many files — low-stakes, reviewed | `gpt-5.4-mini`       | haiku  |
| **medium** | write / implement a well-specified chunk — reviewed via the diff     | `gpt-5.5` (low/med)  | sonnet |

A slightly imperfect read is fine because you review it. Don't delegate a
single-file lookup you'd read faster yourself, or a read where a wrong summary
would mislead you.

## Two ways to delegate

**1. Host-native subagents (preferred when available).** In Claude Code, spawn a
`Task` subagent with a model override — haiku for reads, sonnet for writes. In
Codex, use its native subagents. The worker does the reading and generation, so
that bulk never enters your context.

**2. Cross-CLI worker — `ext-subagent`.** Delegate a coding task to an external
agentic CLI billed separately from your tokens. Run it via Bash from the repo
root:

```
uv run ${CLAUDE_SKILL_DIR}/scripts/ext-subagent.py codex   "Implement X following existing patterns. Run the tests." --model gpt-5.5
uv run ${CLAUDE_SKILL_DIR}/scripts/ext-subagent.py codex   "How does auth work?" --model gpt-5.4-mini --retries 2
echo "Refactor auth to use DI; preserve tests." | uv run ${CLAUDE_SKILL_DIR}/scripts/ext-subagent.py antigravity -
```

In Claude Code, `${CLAUDE_SKILL_DIR}` is already this skill's absolute path; under
another provider, replace the literal placeholder with the directory containing
this SKILL.md.

- Reads → fast tier (`--model gpt-5.4-mini`); writes → medium tier (`--model gpt-5.5`).
- Provider → engine: `codex` → GPT-5.x, `antigravity` → Gemini, `copilot` → Sonnet.
- For long or code-heavy prompts, write the prompt to a file and pass `--prompt-file`
  (or pipe stdin) so you never have to shell-escape it.
- `--retries N` retries with backoff — only for read/answer tasks, **never** for
  file-writing tasks (re-running is not idempotent). `--max-output-chars N` caps the reply.
- `antigravity` has no per-call `--model` (set it in `~/.gemini/antigravity-cli/settings.json`
  or via `agy /model`); passing `--model` to it errors.
- Writes files with auto-approve. `codex` is sandboxed to the workspace; `antigravity`
  and `copilot` are not — review their changes with `git diff` before trusting them.
- Workers get `DELEGATE_INVOKED_SUBAGENT=1` and an instruction to do the task
  directly rather than delegate further; if a worker still calls `ext-subagent`, the
  inherited environment guard refuses the nested call.

## Delegate vs. do it yourself

Delegate substantial, well-specified codegen where a worker drafts and you review,
and any exploration that needs more than a couple of files in context. Write it
yourself only when the logic is subtle enough that reviewing someone else's code
would cost more than writing it.
