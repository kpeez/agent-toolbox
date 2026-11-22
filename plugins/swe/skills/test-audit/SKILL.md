---
name: test-audit
description: "Audit an existing test suite: find missed states, tests that check implementation, duplicates, and checks weaker than the risk needs, then fix the findings the user approves. Use to audit, prune, or review existing tests."
argument-hint: "[tests, path, or diff]"
---

# Test audit

Hold the suite to the behavior it should prove. Every kept check names the
contract it guards and the regression it catches, at the strongest rung that
fits. The rungs and the admission gate live in
[verifying-work](../verifying-work/SKILL.md); the value bar lives in
[test-value](../verifying-work/references/test-value.md). Read
[references/audit.md](references/audit.md) for the detail of each step. For a
whole subsystem, read [references/campaign.md](references/campaign.md) first.

## Scope

Use the caller's tests, path, or diff. Otherwise use the tests that the
current diff against the base branch, default `main`, touches or owns.

## Steps

1. `1-record-suite-baseline`: Before any edit, record each in-scope test's
   pass state and the test line counts at the starting commit. Keep baseline
   failures in their own list.
2. `2-map-the-behavior`: From the production owner, list the public entry
   points, the inputs and outputs, and every state and transition. Done when
   each state and transition has a line.
3. `3-find-flaws`: Mark each test `retain`, `repair`, `consolidate`, or
   `delete` with the evidence fields in the audit reference. Then compare the
   map with the suite. Flag each state or transition that no check reaches,
   and each check on a lower rung than its risk needs, such as example tests
   that one property, type, or end-to-end check would cover. A candidate with
   a missing field is not ready.
4. `4-report-findings`: Report the marks, the missed states, and the weak
   rungs, each with its evidence. Fix only findings the user approved. A
   request that already asks for the fix approves it. Otherwise wait for the
   user's choice.
5. `5-edit-in-small-batches`: Fix the approved findings one coherent
   owner-boundary batch at a time. Delete the test-only seams the removed
   tests kept alive. Add each missing check at the strongest rung through
   `verifying-work`. Rerun the owner and sibling tests after each batch.
   Sequence the batches as in
   [principle-sequence-verifiable-units](../principle-sequence-verifiable-units/SKILL.md).
6. `6-mutate-changed-contracts`: Mutate the production owner of each
   `consolidate`, `repair`, or new contract once. Confirm its keeper fails.
   Restore the source byte for byte. Then run the
   [validation checks](references/audit.md#validation-checks), including the
   repository's required gates.
7. `7-independent-preservation-review`: Get a review of the final diff from
   an agent that did not edit, with the
   [review brief](../../references/review-brief.md). Report an unavailable
   review as a verification gap.
8. `8-publish-draft-pr`: When publication is authorized, push the final
   commits and update the draft PR with [ship-pr](../ship-pr/SKILL.md).
   Otherwise report the reviewed local diff.

Reply with the findings, the fixes made, the tests and production lines
removed, the contracts kept, and the review result. The full handoff list is
in [references/audit.md](references/audit.md#handoff).
