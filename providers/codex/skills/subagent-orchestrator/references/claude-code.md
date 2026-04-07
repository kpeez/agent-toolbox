# Claude Code

Use Claude Code as the first-choice delegate when the task needs the best
overall coding judgment.

## Default Models

- Preferred default: `claude-sonnet-4-6`
- Upgrade for harder tasks: `claude-opus-4-6`
- Built-in alias examples from local help: `sonnet`, `opus`

## Non-Interactive Pattern

Read-only / planning:

```bash
claude -p \
  --model claude-sonnet-4-6 \
  --permission-mode plan \
  --output-format json \
  "Review this repository and return the top 10 architecture risks."
```

Higher-end fallback for hard analysis:

```bash
claude -p \
  --model claude-sonnet-4-6 \
  --fallback-model claude-opus-4-6 \
  --permission-mode plan \
  --output-format json \
  "Trace the data flow for authentication and call out likely failure modes."
```

## Dangerous Mode Equivalent

Claude does not present this as "yolo mode." The closest equivalents are:

- `--dangerously-skip-permissions`
- `--permission-mode bypassPermissions`

Use these only in trusted sandboxes.

## Useful Flags

- `-p`, `--print`: non-interactive mode
- `--output-format json`: structured output for scripting
- `--permission-mode plan`: read-only planning mode
- `--permission-mode acceptEdits`: allow edits without full bypass
- `--add-dir`: expand workspace access
- `--fallback-model`: automatic model fallback in `--print` mode

## Quirks

- `--fallback-model` only works with `--print`.
- `-p` skips the workspace trust dialog, so only use it in directories you
  trust.
- Claude has strong permission controls, but the "dangerous" flags are truly
  broad; keep them rare.

## Good Delegation Prompts

- "Summarize the repo structure in 12 bullets and name the files that matter."
- "Review this diff and list only material correctness risks."
- "Draft an implementation plan for this bug fix without editing files."
