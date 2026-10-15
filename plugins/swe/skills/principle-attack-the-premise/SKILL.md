---
name: principle-attack-the-premise
description: "When two or more fixes that share one premise have failed the same check, stop fixing, write the premise down, and test it before the next fix."
disable-model-invocation: true
---

# Attack the premise

When two or more fixes that share one premise have failed the same check,
suspect the premise, not the fixes. Stop fixing.

Each failed fix is evidence against the belief it assumed. A third fix on the
same premise spends effort where the evidence already says the cause is not.

## Pattern

- **Write the premise down.** The premise is the one sentence that every
  failed fix assumed.
- **Test the premise before the next fix.** Find an observation that would
  come out differently if the premise were false, and make it. Look at how the
  failures are distributed, not only at how large they are. Make the check
  rerunnable, per [build-the-lever](../principle-build-the-lever/SKILL.md).
- **Follow the evidence.** If it contradicts the premise, the cause is
  elsewhere. Look for what the failures have in common that the premise did
  not predict. If it confirms the premise, ask the next "why", per
  [fix-root-causes](../principle-fix-root-causes/SKILL.md). The earlier fixes
  may have treated a consequence instead of the cause.
- **Remove the condition instead of compensating for it**, per the
  [laziness-protocol](../principle-laziness-protocol/SKILL.md). If the
  evidence shows that one part always lands on the losing side, change what
  puts it there. A mechanism that cleans up after it leaves the cause in place
  and adds work on every run.

## Stop

Do not start the next fix before the premise is written down and tested.

This principle is distinct from [redesign-from-first-principles](../principle-redesign-from-first-principles/SKILL.md),
which rebuilds a design around a new requirement. This one questions a fact
that the current design assumes.
