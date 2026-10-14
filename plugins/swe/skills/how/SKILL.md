---
name: how
description: "Explain how code works now: a subsystem's architecture, its runtime flow, or a walkthrough before you change it. Also for placement, ownership, and layering questions such as 'where should this live'. Use why for motivation."
disable-model-invocation: true
---

# How

Explore the codebase to answer "how does X work?" questions. Produce
architectural explanations at the level of a senior engineer onboarding onto a
subsystem. Give enough to build a working mental model. Do not write
annotated source code.

Every spawn is a fresh read-only native subagent. In Claude Code, use the
Agent tool with the `Explore` agent type, or a general-purpose agent told to
edit nothing. Explorers do breadth, so run them on `sonnet`. The explainer
does judgment and prose, so run it on `opus`. In Codex, give explorers medium
reasoning effort and the explainer high. If the host rejects a model, use the
host default and say so.

## 1. Assess complexity

If the scope is ambiguous, state your interpretation and explore. The user can
redirect.

- **Simple** (a single module, a small utility, a narrow question such as "how
  does function X work"). Spawn no explorers. Spawn one explainer that
  explores and explains in one pass. Build its prompt from
  [the explainer prompt](references/explainer-prompt.md) without the explorer
  findings section. Go to step 4.
- **Complex** (a subsystem across several files or services, a cross-cutting
  feature, a full architectural overview). Go to step 2.

When in doubt, take the simple path.

## 2. Explore (complex only)

Split the question into 2 to 4 angles. Each angle is a distinct slice of the
subsystem. Spawn all explorers in a single message. Build each prompt from
[the explorer prompt](references/explorer-prompt.md) with its angle filled in.

## 3. Synthesize (complex only)

When all explorers have returned, spawn one explainer. Build its prompt from
[the explainer prompt](references/explainer-prompt.md) with every explorer's
findings filled in.

## 4. Present

Present the explainer's output. Light edits for clarity or for context from the
conversation are fine. Do not substantially rewrite it.

## Output format

The explanation uses the sections that
[the explainer prompt](references/explainer-prompt.md) defines, and drops any
that do not apply. The sections are Overview, Key Concepts, How It Works, Where
Things Live, and Gotchas.
