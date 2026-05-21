---
name: ship
description: Chain /adversarial-review then /pr on the current branch. Use when branch work is ready to tighten and publish as a draft PR.
---

# /ship - Review, Then Publish

Run the full pre-publish pipeline in one pass: hostile cleanup, then atomic commits + draft PR.

## Command

### /ship [feature-name]

1. **Read and follow** `core/skills/adversarial-review/SKILL.md` (or the installed `adversarial-review/SKILL.md` copy). Pass through the same `[feature-name]` argument. Run the full hostile review — apply fixes, verify, print its summary.
2. **If verification fails**, stop. Do not run `/pr`.
3. **Read and follow** `core/skills/pr/SKILL.md` (or the installed `pr/SKILL.md` copy). Pass through the same `[feature-name]` argument. Group, commit, push, ensure draft PR, write the HTML artifact, update STATUS.
4. **Print a short combined summary**: adversarial-review outcome (files touched, key deletions) + PR outcome (commits, URL, HTML path).

Do not re-derive steps here. The child skills own scope, checklists, commit rules, and artifact format.

## Rules

- **Same feature resolution** for both phases — one optional argument applies to both.
- **Sequential, not parallel.** `/pr` runs only after adversarial-review verification passes.
- **Does not replace native `/review`.** Use the provider's review flow separately when you want a second pass for bugs and edge cases.
