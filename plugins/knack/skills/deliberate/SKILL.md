---
name: deliberate
description: Resolve a two-way decision by commissioning two independent, evidence-based cases — case-for and case-against (or one advocate per option) — then synthesizing a recommendation. Use when weighing two named options or a single yes/no decision, or when the user says "deliberate", "weigh A vs B", "decide between", "should we X", "talk me into/out of it", or "make the case both ways".
---

# Deliberate

Resolve a genuine two-way decision by building the **strongest independent case
on each side**, then synthesizing — not averaging — a recommendation. Use for
**two named options (A vs B)** or a **single yes/no decision** (case-for vs
case-against). One advocate per side.

Invocable directly by the user, and reachable mid-task: when `sharpen` or
`implement` hits a decision branch that needs *agent research* rather than user
input, hand off here.

Keep the interface small: just the decision ("A vs B" / "should we X?"). Infer
stakes, domains, and depth yourself — no flags.

## When to use — and when not to

Use it when the decision is **genuinely uncertain** and getting it right matters
more than speed: a real fork between two options, a reversible-but-consequential
call, a novel situation where pattern-matching fails.

Skip it for subjective taste ("which color"), time-critical calls, trivial
choices, and pure fact-checks (verify instead — debate amplifies persuasion, not
truth). If the decision isn't really two-sided, say so instead of manufacturing
a fake opponent.

## Pick the depth

- **Quick (context-only)** — default for design decisions where the relevant
  evidence is already in front of you. You role-play both cases and the single
  rebuttal in one pass. No subagents.
- **Researched** — for higher-stakes or genuinely uncertain decisions. Spawn two
  *independent* subagents that each research (codebase and/or web) and return
  only their own case.

You choose; don't ask the user to pass a mode.

## The three phases

### 1. Independent cases (mandatory)

Each side builds the strongest case for its position **without seeing the
other's**. In researched mode the two subagents run in parallel and return only
their case — never a critique of the sibling. Independence here is the whole
point: it preserves the diverse starting positions that make two agents worth
the cost. Do not contaminate it.

### 2. One structured rebuttal (capped)

Give each side the opponent's case and let it rebut **once**, under a narrow
mandate: attack the opponent's *evidence* specifically, concede what is genuinely
valid, defend only what survives. This is not free-form debate — open-ended
multi-round argument is where sides converge on a wrong answer and the more
verbose side "wins".

- **Hard cap: one rebuttal per side, then stop.** No third round.
- Wiring: by default, **re-spawn** a rebuttal pass per side (you hold both cases
  in context — hand each its own case plus the opponent's). If the harness
  supports continuing a spawned agent with context intact, send each phase-1
  agent the opponent's case instead — cheaper, keeps its research context. Fall
  back to re-spawn when continuation isn't available.

### 3. Synthesis (do not split the difference)

Summarize each case faithfully, then **weigh evidence quality, not volume** —
judges over-reward verbosity and vivid-but-wrong arguments. Output in this shape:

- **Shared ground** — what both sides agree on.
- **Real disagreements** — where the evidence actually diverges.
- **Which side's evidence is stronger, and why** — per dimension.
- **Recommendation + confidence.**

Discipline:

- Conceding a valid point counts as a **strength**, not a loss.
- A rebuttal that is assertion with no new evidence counts for nothing.
- **"Both cases are weak" is a valid outcome, not a failure.** When neither side
  marshals strong evidence, recommend gathering more data or deciding on
  competing values — and say so explicitly. No false balance.

## Record durable outcomes

When a deliberation resolves a decision for a load-bearing reason a future review
would otherwise re-raise, record it as an ADR using `sharpen`'s
[ADR-FORMAT.md](../sharpen/ADR-FORMAT.md). Reuse that seam — don't invent a
bespoke decision-record format. Skip recording for ephemeral or self-evident
reasons.

Use the `documentation` skill's Markdown guidance for any written output: lead
with the recommendation, keep evidence close to the claim it supports.
