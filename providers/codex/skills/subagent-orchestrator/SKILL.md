---
name: subagent-orchestrator
description: Teach Codex to delegate bounded coding tasks to other AI CLIs such as Claude Code, Gemini CLI, and Copilot CLI, then review the results fairly, retry on provider limits, and fall back cleanly while Codex remains the orchestrator.
---

# Subagent Orchestrator

Use this skill when Codex should offload bounded work to another AI CLI to save
Codex usage, get a second opinion, or parallelize repo exploration while still
keeping Codex in charge.

Codex remains the orchestrator. The external model is a worker, not the final
authority.

Load these files only as needed:

- `references/provider-ranking.md`
- `references/context-assembly.md`
- `references/claude-code.md`
- `references/gemini-cli.md`
- `references/copilot-cli.md`
- `scripts/provider_state.py`

## Default Recommendation

Start with one Codex-specific skill, not a generalized delegate-everyone-to-
everyone system.

The first-pass provider order is:

1. Claude Code
2. Gemini CLI
3. Copilot CLI

That ordering is a practical recommendation for Codex subagent work, not a
universal benchmark. Load `references/provider-ranking.md` when you need the
research notes, citations, or task-routing detail.

## Good Delegation Targets

- repo exploration
- architecture summary
- code review
- draft implementation plan
- test ideas
- second-opinion analysis

Avoid delegating the final decision, final merge judgment, or open-ended product
ownership. Codex should keep those.

## Default Workflow

### 1. Bound the task

Give the subagent a narrow ask with an explicit output shape. Good prompts ask
for a summary, risk list, draft patch plan, or focused review.

### 2. Enrich the prompt

Do not pass thin prompts through unchanged.

Turn something like:

```text
Review this repository and summarize the main risks.
```

into a delegation packet that states:

- the goal of the task
- what success looks like
- what failure looks like
- the exact output shape you want back
- which relevant skills the subagent should use
- which files or directories to read first
- any small file chunks or notes that should be attached inline

Load `references/context-assembly.md` when building the delegation packet.

At minimum, enrich the prompt with:

- task goal: why Codex is delegating this
- success criteria: what would make the answer useful
- failure criteria: what would make the answer unusable
- domain hints: repo type, framework, vault, spec workflow, or review stance
- relevant skills: for example, use Obsidian-related skills if the repo is an
  Obsidian vault
- context to inspect first: `AGENTS.md`, `README.md`, `specs/`, or a short file
  list chosen by Codex

Prefer short curated context over dumping the entire repo. If a few files define
the problem, name those files first. If a file contains one relevant section,
quote or summarize only that chunk instead of pasting the whole file.

If the repo has a `specs/` directory or spec-linked workflow, tell the
subagent where the relevant spec lives and whether it should read spec files
before touching code.

### 3. Pick a provider

Check the current provider state:

```bash
python3 skills/subagent-orchestrator/scripts/provider_state.py pick
```

Use the default routing unless there is a strong reason not to:

- Claude Code for the best first-pass repo analysis and nuanced code review
- Gemini CLI for low-cost broad scans, long-context reading, and cheap retries
- Copilot CLI when GitHub-native context or existing Copilot budget makes it a
  better fit

### 4. Run the provider non-interactively

Use the provider reference file for the exact flags. Prefer read-only or
planning modes for exploration work. Only use the provider's yolo or dangerous
mode inside a trusted sandbox and only when the task truly needs edits or shell
actions.

### 5. Review the result fairly

Start from the assumption that the subagent may have done good work.

- Accept it when it is solid. `LGTM` is allowed.
- Lightly edit when the answer is mostly right.
- Retry when the prompt was underspecified.
- Reject or fall back only when the result is materially wrong, risky, or the
  provider is unavailable.

Do not be pedantic for its own sake. Be critical only where it changes the
outcome.

### 6. Handle provider failures

If the CLI indicates rate limits, usage caps, temporary overload, or "try again
later", cool that provider down and pick another one.

Typical cooldown flow:

```bash
python3 skills/subagent-orchestrator/scripts/provider_state.py mark-failure \
  --provider claude-code \
  --reason "rate limit exceeded" \
  --cooldown-minutes 30

python3 skills/subagent-orchestrator/scripts/provider_state.py pick
```

If the failure is auth, bad config, or a missing executable, do not treat that
as a transient provider outage. Surface the setup issue instead.

### 7. Record the verdict

When Codex reports back, include:

- provider and model used
- delegated task
- verdict: accepted, edited, retried, or rejected
- any follow-up action

## Prompt-Building Rules

When preparing a subagent prompt, Codex should gather and pass only the context
that materially improves the result.

- Always mention the task goal explicitly.
- Always define what success looks like and what failure looks like.
- Name the relevant skills the subagent should use when the repo has a known
  domain. Example: use obsidian-related skills when working in an Obsidian
  vault.
- Point the subagent to the files that matter first. Usually that means a short
  ordered list, not a giant dump.
- If `AGENTS.md`, `README.md`, or `specs/` are relevant, say so directly.
- Attach short chunks only when they remove ambiguity. Prefer 10-40 important
  lines over whole-file paste.

Useful context sources:

- repo instructions such as `AGENTS.md`
- `README.md`
- relevant `specs/` files
- files named by the user
- a short handpicked list of code files that define the task

If the task is "review this repo," Codex should still state what kind of review
it wants: correctness risks, architecture risks, code quality issues, test
gaps, or implementation plan. "Review" without a frame is too vague.

## Delegation Packet Shape

Use a shape like this:

```text
Goal:
Success looks like:
Failure looks like:
Return format:
Relevant skills or domain hints:
Files to read first:
Attached context:
Task:
```

Codex can keep the packet brief, but it should not omit those fields when the
task would benefit from them.

## Failure Heuristics

Treat these as likely transient and eligible for cooldown:

- `rate limit`
- `usage limit`
- `quota`
- `overloaded`
- `capacity`
- `try again later`
- `temporarily unavailable`

Treat these as setup problems, not cooldown signals:

- `not authenticated`
- `command not found`
- `invalid api key`
- `permission denied`
- malformed CLI arguments

## Output Expectations

The point of delegation is to save Codex effort without lowering standards.
Codex should use the subagent output as input to judgment, not as a substitute
for judgment.
