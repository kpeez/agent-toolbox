# Provider Ranking

Research date: April 6, 2026.

This ordering is a recommendation for Claude-as-orchestrator workflows. It is
based on current official docs, local CLI help in this environment, and
practical tradeoffs across quality, CLI ergonomics, cost/value, speed, and
session-limit behavior.

## Ranking

### 1. Codex CLI

Best default choice for delegated coding and reasoning work.

Why it ranks first:

- Strong 5.x model lineup: `gpt-5.4-med` for moderate tasks, `gpt-5.4-high`
  for hard reasoning, and the optional `5.3-codex-high` coding specialist.
- Mature non-interactive flow via `codex exec` with explicit sandbox policies,
  model selection, and output capture.
- Built-in code review subcommand (`codex exec review`) for dedicated review
  tasks.

Best use:

- implementation and code writing
- code review
- difficult reasoning and analysis
- draft implementation plans

Watch-outs:

- `codex exec` is the non-interactive entry, not `-p` (which means `--profile`)
- no `--output-format json`; use `-o FILE` for final message capture
- `5.3-codex-high` is optional and coding-focused; default to `gpt-5.4-med`
  for general work
- usage limits and rate limits still apply

### 2. Gemini CLI

Best value fallback and strong default for cheap, broad, long-context work.

Why it ranks second:

- Official docs emphasize Gemini 2.5 Pro, a 1M-token context window, and a free
  tier with 60 requests per minute and 1,000 requests per day for personal
  Google accounts.
- Good non-interactive scripting support with `-p`, JSON output, explicit model
  selection, and a true plan mode.
- Excellent fit for wide repository summaries, docs digestion, and low-cost
  retries when Codex is capped.

Best use:

- long-context reading
- repo scans
- cheap retries
- draft summaries
- second-opinion analysis

Watch-outs:

- model control depends on auth method; API key mode is the clearest path when
  you need exact model selection
- quality is strong, but Codex is still preferred for the most subtle review
  tasks

### 3. Copilot CLI

Useful situational delegate, not the default cheap subagent.

Why it ranks third:

- It exposes strong models and good CLI controls, but its best fit is often
  "already inside a GitHub-centric workflow" rather than "lowest-friction cheap
  delegate from Claude."
- Official docs and local help show strong model optionality, but the premium
  request and entitlement story is more variable than Gemini's published free
  tier or a direct Codex subscription.
- Best when GitHub context, MCP tooling, or existing Copilot spend makes it the
  natural choice.

Best use:

- GitHub-heavy workflows
- cases where Copilot is already the paid path you are using
- situations where you want model choice inside one GitHub-managed tool

Watch-outs:

- premium-request budgeting can make it less predictable as the default
  "savings" delegate
- permission setup for non-interactive runs is more explicit than Gemini or
  Codex

## Task Routing

- Use Codex CLI first for difficult reasoning, coding tasks, and subtle code
  judgment.
- Use Gemini CLI first when you want low-cost breadth, very large context, or a
  cheap retry path.
- Use Copilot CLI first only when GitHub-native context or an existing Copilot
  budget is the main constraint.

## Sources

- Codex CLI help: `codex exec --help` (local, April 6, 2026)
- Gemini CLI overview: <https://google-gemini.github.io/gemini-cli/>
- Gemini CLI configuration: <https://google-gemini.github.io/gemini-cli/docs/get-started/configuration.html>
- GitHub Copilot CLI docs hub: <https://docs.github.com/en/copilot/how-tos/copilot-cli>
- GitHub Copilot CLI command reference: <https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference>
- GitHub Copilot premium request management: <https://docs.github.com/en/copilot/concepts/billing/premium-request-management>
- GitHub Agentic Workflows engine reference: <https://github.github.com/gh-aw/reference/engines/>

## Notes

- The ordering above is an inference from the sources, not a vendor-published
  benchmark.
- Local CLI help on April 6, 2026 matched the flags documented for the
  installed `codex`, `gemini`, and `copilot` binaries in this environment.
