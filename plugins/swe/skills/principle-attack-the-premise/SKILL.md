---
name: principle-attack-the-premise
description: "When two or more fixes that share one premise have failed the same check, stop fixing, take a census of where the failure sits, and question the premise."
disable-model-invocation: true
---

# Attack the premise

When two or more fixes that share one premise have failed the same check,
suspect the premise, not the fixes. Stop fixing.

Each failure under a shared premise is evidence about the premise.

## Pattern

- **Write the premise down.** The premise is the one sentence that every
  failed fix assumed.
- **Take a census before the next fix.** Count the imbalance per actor, input,
  or run. The census shows which actors hold the imbalance, not how large it
  is. Write the census as a rerunnable script, per [build-the-lever](../principle-build-the-lever/SKILL.md).
- **Read the skew.** If the same few actors hold most of the imbalance on
  every run, something assigns them that role. Find what assigns the role.
  That assignment is the next "why", per [fix-root-causes](../principle-fix-root-causes/SKILL.md).
- **Remove the asymmetry instead of compensating for it**, per the
  [laziness-protocol](../principle-laziness-protocol/SKILL.md). Rotate the role between actors, randomize the
  assignment, or move the role, so that no actor holds it on every run. A
  return path, a shared pool, a batched hand-off, or a periodic rebalance
  leaves the assignment in place and adds work on every run.

## Stop

- Do not start the next fix before the premise is written down and the census
  exists.
- If the census is even across actors, the premise is not the cause. Look for
  the cause elsewhere and keep the census as evidence.

This principle is distinct from [redesign-from-first-principles](../principle-redesign-from-first-principles/SKILL.md),
which rebuilds a design around a new requirement. This one questions a fact
that the current design assumes.
