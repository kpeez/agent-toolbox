---
name: writing
description: "Write or edit prose: a README, a docs page, a skill or AGENTS.md, a PR body, a commit message, a handoff, a plan, or a reply. Use when you create or edit one, or when a change makes one stale."
argument-hint: "<document or path>"
---

# Writing

All writing advice lives here. Follow these steps.

1. `1-find-the-surface`: Find the surface of the text in the table below.
2. `2-read-its-row`: Read what its row names.
3. `3-apply-the-prose-rules`: Apply the [prose rules](references/prose.md) to
   every surface.

| Surface | Read |
| --- | --- |
| README, docs page, plugin guide | [human docs](references/human-docs.md) |
| Skill, `AGENTS.md`, `CLAUDE.md`, agent brief | [writing-for-agents](../writing-for-agents/SKILL.md), and the ASD-STE100 section of the prose rules |
| PR body, commit message | [PR body](../ship-pr/references/pr-body.md) |
| Handoff, plan | its rules ([handoff](../handoff/SKILL.md), [plan-multi-phase](../swe-mode/playbooks/plan-multi-phase.md), [html-plan](../html-plan/SKILL.md) for a plan the user reviews in a browser), [show-me](references/show-me.md) for a design or a change, and the ASD-STE100 section |
| Reply to the user | the ASD-STE100 section; [show-me](references/show-me.md) when the reply explains a design |
| Code comment | only a non-obvious why ([no-comments](../no-comments/SKILL.md)) |

## Rules for every surface

- The [prose rules](references/prose.md) own the AI patterns (rule numbers are
  stable ids), sentence rhythm, the STE and Global English rules, and the
  ASD-STE100 rules for replies and agent-facing text. Check every rule against
  the whole text, and rewrite each hit or keep it on purpose.
- [show-me](references/show-me.md) owns the visuals that explain code. The
  [PR body](../ship-pr/references/pr-body.md) has its own copy of the menu.
  Use the smallest visual that makes the point.
- When a new jargon word turns up, propose it and its replacement in your
  reply as an addition to rule 26, with the diff.
