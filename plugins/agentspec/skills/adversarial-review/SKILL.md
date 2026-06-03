---
name: adversarial-review
description: Run an adversarial review in a fresh reviewer with no memory of this conversation — challenge the approach, design, tradeoffs, and assumptions, not just defects. Review-only. Use before /pr or native code review.
---

# /adversarial-review - Challenge the Approach

Delegate the review to a fresh `codex` reviewer that sees only the diff, never this
conversation — the author can't critique their own choices honestly. It challenges the
chosen approach, design, tradeoffs, and assumptions, not just defects.

Review-only: return the reviewer's output verbatim. Do not fix anything.

## /adversarial-review [--base <ref>] [focus ...]

1. **Base**: `--base <ref>` if given, else `git merge-base main HEAD` (fall back to `master`).
2. **Run**: substitute `<base>` and append any `focus` text into the prompt below, write it to a temp file, and run `ext-subagent codex --prompt-file <file>` (see `delegating-work`).
3. **Return** the reviewer's stdout verbatim. `/ship` applies fixes afterward.

## Review Prompt

```text
Adversarially review this branch against <base>. The diff is guilty until proven
innocent; bias toward deletion. Inspect it yourself: `git diff <base>` plus untracked
files from `git ls-files --others --exclude-standard`.

Challenge the work, don't just nitpick:
- Is this the right approach, or just the first one? What simpler path was skipped?
- What unstated or unverified assumptions does it depend on?
- Where does it break under real conditions — scale, concurrency, bad input, partial failure?
- What did the tradeoffs cost (coupling, perf, readability, testability)?
- Does it fit existing patterns, or duplicate something the repo already does?
- Flag bloat, over-abstraction, duplication, dead code, and code it makes obsolete.

Review-only: report findings, fix nothing. End with a verdict: ship as-is | revise before PR | rethink approach.
```
