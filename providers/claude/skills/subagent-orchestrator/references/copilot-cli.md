# Copilot CLI

Use Copilot CLI when GitHub-native context or existing Copilot budget makes it a
natural delegate, not as the default first pick for cheap subagent work.

## Default Models

Strong models exposed by current local help include:

- `claude-sonnet-4.6`
- `claude-opus-4.6`
- `gpt-5.4`
- `gpt-5.4-mini`

Practical default:

- Preferred default: `claude-sonnet-4.6`
- Cheap fallback: `gpt-5.4` (high or medium)

## Non-Interactive Pattern

Read-only-ish analysis in the current repo:

```bash
copilot -p "Review this repository and summarize the main risks." \
  --model claude-sonnet-4.6 \
  --output-format json \
  --allow-all-tools \
  --no-ask-user
```

If you want the fully permissive equivalent:

```bash
copilot -p "Review this repository and summarize the main risks." \
  --model claude-sonnet-4.6 \
  --output-format json \
  --allow-all
```

## Yolo Mode

Copilot has explicit permissive shortcuts:

- `--allow-all`
- `--yolo`

Both map to:

- `--allow-all-tools`
- `--allow-all-paths`
- `--allow-all-urls`

## Useful Flags

- `-p`, `--prompt`: non-interactive mode
- `--model`: explicit model selection
- `--output-format json`: JSONL output
- `--allow-all-tools`: required for smooth non-interactive tool use
- `--no-ask-user`: keep the agent autonomous
- `--add-dir`: expand path access

## Quirks

- Permission controls are explicit and a bit more verbose than Gemini's.
- Premium request usage can make Copilot a less predictable default "money
  saver" than Gemini's published free tier or a direct Claude subscription.
- Copilot can still be excellent when the surrounding workflow is already
  GitHub-centric.

## Good Delegation Prompts

- "Review this repository with GitHub workflow assumptions in mind."
- "Summarize the likely CI and PR risks in this codebase."
- "Give me a second opinion using Copilot's current model stack."
