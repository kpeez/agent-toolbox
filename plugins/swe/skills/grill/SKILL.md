---
name: grill
description: Grill the user about a plan, design, or decision until every branch is resolved. Use when the user asks to be grilled, wants their thinking stress-tested, or wants holes poked in an idea.
---

Interview the user relentlessly until you reach a shared understanding. Map the
work as a **design tree**: every decision branches into the decisions that hang
off it.

Work the tree in **rounds**. The **frontier** is every decision whose
prerequisites are settled: the questions you can ask now without guessing at
answers you have not heard. Ask the whole frontier in one round, each question
with your recommended answer, then wait for the answers. Each answer moves the
frontier outward; recompute it and ask the next round. A question that depends
on another question still open in this round belongs to a later round.

## Asking a round

When the host has a built-in tool for asking the user questions, ask the round
through it: one question per frontier decision, your recommendation as the
first option and labeled "(Recommended)", and the real alternatives as the
other options. When the frontier exceeds the tool's per-call limit, ask first
the decisions that unblock the most others and carry the rest to the next
round. Ask open-ended questions, which have no short set of answers, in text.

Without such a tool, write the round in text, and word each question so "yes"
accepts your recommendation:

```
❓ **Q1 · <short-slug>**: <question, with the choices when they exist>

➡️ <recommended answer>

---

❓ **Q2 · <short-slug>**: <question>

➡️ <recommended answer>
```

## Facts and decisions

Finding facts is your job, never the user's. When a frontier question needs a
fact from the code, documents, or tools, look it up, and dispatch a subagent for
a substantial search. A running lookup holds back only the questions that
depend on it; ask the rest of the frontier now. Check the user's claims about
current behavior against the code, and put any contradiction in the next round.

The decisions are the user's: put each one to them and wait.

When a term is vague or overloaded, propose one precise term as a frontier
question. Check it against `.agents/docs/CONTEXT.md` when that glossary exists.

## Done

The session is done when the frontier is empty: every branch visited, nothing
silently assumed. Summarize the settled decisions, the alternatives rejected and
why, and any decision left open with its owner. Act on the result only after the
user confirms the shared understanding.

When a settled term is reusable, or a decision meets the criteria in the
[ADR format](../../references/ADR-FORMAT.md), offer to record it as a glossary
entry ([context format](../../references/CONTEXT-FORMAT.md)) or an ADR.
