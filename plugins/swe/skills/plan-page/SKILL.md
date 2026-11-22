---
name: plan-page
description: "Show a plan, design, or set of options as one HTML page the user reads and answers on a phone. Use when the user must read a plan before deciding, or asks for an HTML plan."
argument-hint: "[plan or decisions]"
---

Turn a plan into one self-contained HTML page. The user reads it and settles
each decision. The page needs no server.

## 1-copy-the-template

Copy [`references/template.html`](references/template.html) into the
branch's scratch folder, as set out in
[agent scratch](../../references/agent-scratch.md). Name the copy for the
plan, such as `plan.html`.

## 2-fill-the-page

Fill in the copy: the title, the goal, the plan sections, and one
`fieldset.decision` for each open decision. Give each decision a unique id
(`d1`, `d2`, and so on), its options, and one recommended option. Keep the
inline CSS and JS. Add no external asset and no network call.

## 3-show-the-page

Give the page to the user the way the user's own instructions say to show an
HTML file. When no instruction says how, give the file path.

## 4-settle-the-decisions

Settle the decisions one of two ways:

- Interview the user in chat, with `interview-user`.
- The user taps answers on the page and pastes the copy block back.

The copy block has one line for each decision:

```
d1: Option text | note: the user's note
d2: (no answer)
```

Treat a pasted block as the user's answers. Ask about each `(no answer)`
line, or take your recommended option and say so.
