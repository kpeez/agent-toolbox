# Provider Ranking

Research date: April 3, 2026.

This ordering is a recommendation for Codex-as-orchestrator workflows. It is
based on current official docs, local CLI help in this environment, and
practical tradeoffs across quality, CLI ergonomics, cost/value, speed, and
session-limit behavior.

## Ranking

### 1. Claude Code

Best default choice for high-value delegated coding work.

Why it ranks first:

- Strongest default for deep repo exploration, architecture reading, and
  nuanced code review.
- Mature non-interactive CLI flow with explicit `--print`,
  `--output-format json`, `--permission-mode`, and `--fallback-model`.
- Model naming is clear for subagent use: `claude-sonnet-4-6` and
  `claude-opus-4-6` are straightforward targets.

Best use:

- repo exploration
- architecture review
- code review
- difficult implementation planning

Watch-outs:

- usage limits and temporary overload still happen
- dangerous-mode equivalents should stay sandbox-only

### 2. Gemini CLI

Best value fallback and strong default for cheap, broad, long-context work.

Why it ranks second:

- Official docs emphasize Gemini 2.5 Pro, a 1M-token context window, and a free
  tier with 60 requests per minute and 1,000 requests per day for personal
  Google accounts.
- Good non-interactive scripting support with `-p`, JSON output, explicit model
  selection, and a true plan mode.
- Excellent fit for wide repository summaries, docs digestion, and low-cost
  retries when Claude is capped.

Best use:

- long-context reading
- repo scans
- cheap retries
- draft summaries
- second-opinion analysis

Watch-outs:

- model control depends on auth method; API key mode is the clearest path when
  you need exact model selection
- quality is strong, but I would still prefer Claude first for the most subtle
  review tasks

### 3. Copilot CLI

Useful situational delegate, not my default cheap subagent.

Why it ranks third:

- It exposes strong models and good CLI controls, but its best fit is often
  "already inside a GitHub-centric workflow" rather than "lowest-friction cheap
  delegate from Codex."
- Official docs and local help show strong model optionality, but the premium
  request and entitlement story is more variable than Gemini's published free
  tier or a direct Claude subscription.
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
  Claude

## Task Routing

- Use Claude Code first for difficult reasoning, repo review, and subtle code
  judgment.
- Use Gemini CLI first when you want low-cost breadth, very large context, or a
  cheap retry path.
- Use Copilot CLI first only when GitHub-native context or an existing Copilot
  budget is the main constraint.

## Sources

- Anthropic Claude Code settings: <https://code.claude.com/docs/en/settings>
- Anthropic Claude Code security: <https://code.claude.com/docs/en/security>
- Gemini CLI overview: <https://google-gemini.github.io/gemini-cli/>
- Gemini CLI configuration: <https://google-gemini.github.io/gemini-cli/docs/get-started/configuration.html>
- GitHub Copilot CLI docs hub: <https://docs.github.com/en/copilot/how-tos/copilot-cli>
- GitHub Copilot CLI command reference: <https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference>
- GitHub Copilot premium request management: <https://docs.github.com/en/copilot/concepts/billing/premium-request-management>
- GitHub Agentic Workflows engine reference: <https://github.github.com/gh-aw/reference/engines/>

## Notes

- The ordering above is an inference from the sources, not a vendor-published
  benchmark.
- Local CLI help on April 3, 2026 matched the flags documented for the
  installed `claude`, `gemini`, and `copilot` binaries in this environment.
