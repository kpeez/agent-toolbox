---
name: delegate
description: Delegate token-heavy work to cheaper workers instead of doing it yourself — route reads/exploration to an explorer, plan/design drafting to a planner, and well-specified codegen to a doer, then review what comes back. Use whenever you are about to read many files to answer a question, draft a plan or spec, or write a substantial, well-specified chunk of code — including from within /start-loop, /implement, /tdd, /diagnose, and /improve-codebase-architecture.
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

| Role         | Use for                                                                        | Codex                    | Claude                 | Gemini       |
| ------------ | ------------------------------------------------------------------------------- | ------------------------- | ----------------------- | ------------ |
| **explorer** | reads / exploration / summarize across many files — low-stakes, reviewed        | `gpt-5.6-luna` (medium)  | haiku                   | `gemini-3.5` |
| **doer**     | write / implement a well-specified chunk — reviewed via the diff                | `gpt-5.6-luna` (xhigh)   | sonnet (or opus, low)   | —            |
| **planner**  | plan drafting, design review, spec critique — judgment quality dominates cost   | `gpt-5.6-sol`            | fable / opus (high)     | —            |

A slightly imperfect read is fine because you review it. Don't delegate a
single-file lookup you'd read faster yourself, or a read where a wrong summary
would mislead you.

Route by kind of work: exploration → **explorer**, plan/design drafting →
**planner**, well-specified codegen → **doer**. Planners return proposals for
the lead agent to review with the user — subagents never converse with the
user directly.

Give every **planner** and **doer** its own `/goal` — a one-line verifiable end
state for its task. **Explorers are exempt**: a read has a question, not an end
state; skip the goal ceremony for lookups.

## Two ways to delegate

**1. Host-native subagents (preferred when available).** In Claude Code, spawn a
`Task` subagent with a model override — haiku for explorer reads, sonnet for doer
writes, fable/opus for planner drafts. In Codex, use its native subagents. The
worker does the reading, drafting, and generation, so that bulk never enters your
context.

**2. Cross-CLI worker — `ext-subagent`.** Delegate a coding task to an external
agentic CLI billed separately from your tokens. Run it via Bash from the repo
root:

```
uv run ${CLAUDE_SKILL_DIR}/scripts/ext-subagent.py codex   "Implement X following existing patterns. Run the tests." --role doer
uv run ${CLAUDE_SKILL_DIR}/scripts/ext-subagent.py codex   "How does auth work?" --role explorer --retries 2
echo "Refactor auth to use DI; preserve tests." | uv run ${CLAUDE_SKILL_DIR}/scripts/ext-subagent.py antigravity -
```

In Claude Code, `${CLAUDE_SKILL_DIR}` is already this skill's absolute path; under
another provider, replace the literal placeholder with the directory containing
this SKILL.md.

- `--role explorer|doer|planner` (codex) expands to the tier's model + reasoning
  effort — prefer it over hand-picking `--model`/`--reasoning-effort`.
- Provider → engine: `codex` → GPT-5.x, `antigravity` → Gemini, `copilot` → Sonnet.
- Workers are killed after `--timeout` seconds (default 1800). Raise it — or pass
  `--timeout 0` to disable — for tasks expected to run long. An exit-0 run with an
  empty answer is reported as a failure (and retried under `--retries`).
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
