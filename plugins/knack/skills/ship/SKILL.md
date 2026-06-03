---
name: ship
description: Chain /adversarial-review then /pr on the current branch. Use when branch work is ready to tighten and publish as a draft PR.
---

# /ship - Review, Fix, Then Publish

Run the full pre-publish pipeline in one pass: clean-context hostile review, apply the
fixes, verify, then atomic commits + draft PR.

## Command

### /ship [feature-name]

1. **Read and follow** `skills/adversarial-review/SKILL.md` (or the installed `adversarial-review/SKILL.md` copy). Pass through the same `[feature-name]` argument. This produces the review Findings — it is review-only and applies no fixes.
2. **If the verdict is `rethink approach`** or any design risk is blocking, stop and surface the Findings to the user. Do not apply fixes or run `/pr` without their call.
3. **Apply the fixes yourself** from the Findings — rewrite, inline, delete per the kill list and simplifications, and resolve the design risks you agree with. Skip any recommendation you judge wrong, and say why.
4. **Verify**: run lint, type checks, and tests (use the Findings' "Verify after fixes" commands). If verification fails, stop. Do not run `/pr`.
5. **Read and follow** `skills/pr/SKILL.md` (or the installed `pr/SKILL.md` copy). Pass through the same `[feature-name]` argument. Group, commit, push, ensure draft PR, write the markdown artifact, update STATUS.
6. **Print a short combined summary**: review outcome (verdict, key fixes applied/skipped) + PR outcome (commits, URL, markdown artifact path).

Do not re-derive steps here. The child skills own scope, checklists, commit rules, and artifact format.

## Rules

- **Same feature resolution** for both phases — one optional argument applies to both.
- **Sequential, not parallel.** Review → fix → verify → `/pr`, in order.
- **The review is review-only.** Fixing is `/ship`'s job, between the review and `/pr`.
- **Does not replace native `/review`.** Use the provider's review flow separately when you want a second pass for bugs and edge cases.
