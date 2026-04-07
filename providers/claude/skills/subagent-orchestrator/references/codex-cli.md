# Codex CLI

Use Codex CLI as the first-choice delegate when the task needs strong coding
judgment or difficult reasoning.

## Default Models

- Preferred default: `gpt-5.4-med` (moderate tasks)
- Upgrade for harder tasks: `gpt-5.4-high`
- Optional coding specialist: `5.3-codex-high` (strong at hard/moderate coding)

## Non-Interactive Pattern

Read-only exploration:

```bash
codex exec \
  "Review this repository and return the top 10 architecture risks." \
  -m gpt-5.4-med \
  -s read-only \
  -o /tmp/codex-result.txt
```

Higher-end fallback for hard analysis:

```bash
codex exec \
  "Trace the data flow for authentication and call out likely failure modes." \
  -m gpt-5.4-high \
  -s read-only \
  -o /tmp/codex-result.txt
```

Auto-write sandbox for implementation work:

```bash
codex exec \
  "Implement the changes described in specs/feature/design.md." \
  -m gpt-5.4-med \
  --full-auto
```

## Dangerous Mode Equivalent

Codex provides:

- `--dangerously-bypass-approvals-and-sandbox`

Use this only in trusted, externally sandboxed environments.

## Useful Flags

- `exec`: non-interactive subcommand (NOT `-p`, which means `--profile`)
- `-m`, `--model`: explicit model selection
- `-s`, `--sandbox`: sandbox policy (`read-only`, `workspace-write`,
  `danger-full-access`)
- `--full-auto`: convenience alias for `-a on-request --sandbox workspace-write`
- `-o`, `--output-last-message`: write the final agent message to a file
- `--json`: JSONL event stream to stdout (streaming, not a single JSON blob)
- `-C`, `--cd`: set working directory
- `--add-dir`: additional writable directories
- `--ephemeral`: no session persistence
- `--skip-git-repo-check`: allow running outside a git repo
- `--output-schema`: path to JSON Schema for structured output

## Dedicated Review

Codex has a built-in code review mode:

```bash
codex exec review
```

This runs a non-interactive code review against the current repository.

## Quirks

- `codex exec` is the non-interactive entry point, not `-p`. The `-p` flag on
  the main `codex` command means `--profile` (config profile), not print mode.
- There is no `--output-format json` flag. Use `--json` for JSONL streaming
  events or `-o FILE` to capture just the final message. For subagent use,
  prefer `-o` since it gives you the answer without parsing a stream.
- `--full-auto` combines `-a on-request` with `--sandbox workspace-write`.
  Good for implementation tasks in a sandboxed environment.
- Stdin is supported: if no prompt argument is given (or `-` is used),
  instructions are read from stdin. If stdin is piped and a prompt is also
  provided, stdin is appended as a `<stdin>` block.

## Good Delegation Prompts

- "Review this diff and list only material correctness risks."
- "Implement the function described in this spec, writing files as needed."
- "Draft an implementation plan for this bug fix without editing files."
