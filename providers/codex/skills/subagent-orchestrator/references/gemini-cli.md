# Gemini CLI

Use Gemini CLI as the best value delegate and the default fallback when Claude
is capped or when you want broad, cheap exploration.

## Default Models

- Preferred default: `gemini-2.5-pro`
- Cheaper fast pass: `gemini-2.5-flash`

## Non-Interactive Pattern

Read-only / planning:

```bash
gemini -p \
  "Review this repository and summarize the architecture in 10 bullets." \
  -m gemini-2.5-pro \
  --approval-mode plan \
  --output-format json
```

Cheap wide scan:

```bash
gemini -p \
  "Scan this repository and list the most suspicious files for auth bugs." \
  -m gemini-2.5-flash \
  --approval-mode plan \
  --output-format json
```

## Yolo Mode

Gemini has an explicit yolo mode:

- `--yolo`
- `--approval-mode yolo`

It also supports:

- `--approval-mode auto_edit`
- `--approval-mode plan`

Gemini's docs note that sandboxing is enabled by default when using yolo mode.

## Useful Flags

- `-p`, `--prompt`: non-interactive mode
- `-m`, `--model`: explicit model selection
- `--output-format json`: structured output
- `--approval-mode plan`: read-only planning mode
- `--include-directories`: expand workspace scope

## Quirks

- Google login is the cleanest path for generous default usage, but API key mode
  is the clearest path when you need strict model control.
- Gemini is especially attractive for large-context reads because the official
  docs emphasize Gemini 2.5 Pro with a 1M-token context window.

## Good Delegation Prompts

- "Read the whole repo and group modules by responsibility."
- "Give me a low-cost second opinion on whether this refactor is safe."
- "List likely bug clusters without proposing a patch yet."
