---
name: writing
description: "Write or edit prose: a README, a docs page, a skill or AGENTS.md, a PR body, a commit message, a handoff, a plan, or a reply. Use when you create or edit one, or when a change makes one stale."
---

# Writing

All writing advice lives here. Find the surface, read what its row names, and
apply the [prose rules](references/prose.md) to every surface.

| Surface | Read |
| --- | --- |
| README, docs page, plugin guide | [human docs](references/human-docs.md) |
| Skill, `AGENTS.md`, `CLAUDE.md`, agent brief | [writing-for-agents](../writing-for-agents/SKILL.md), and the ASD-STE100 section of the prose rules |
| PR body, commit message | [PR body](../ship-pr/references/pr-body.md) and [show-me](references/show-me.md) |
| Handoff, plan | its rules ([handoff](../handoff/SKILL.md), [plan-multi-phase](../swe-mode/references/plan-multi-phase.md)), [show-me](references/show-me.md) for a design or a change, and the ASD-STE100 section |
| Reply to the user | the ASD-STE100 section; [show-me](references/show-me.md) when the reply explains a design |
| Code comment | only a non-obvious why ([no-comments](../no-comments/SKILL.md)) |

## Rules for every surface

- The [prose rules](references/prose.md) own the AI patterns (rule numbers are
  stable ids), sentence rhythm, the STE and Global English rules, and the
  ASD-STE100 rules for replies and agent-facing text.
- [show-me](references/show-me.md) owns the visuals that explain code: real
  code, pseudocode, call trees, file trees, Mermaid, diff sketches, and the
  one-way or two-way door.
- When a new jargon word turns up, propose it and its replacement in your
  reply as an addition to rule 26, with the diff.

## Check

Done when every item holds:

- The text follows the file its surface row names.
- Every rule in the prose rules is checked against the whole text, and each
  hit is rewritten or deliberately kept.
- A visual, when present, is the smallest one that makes the point.
