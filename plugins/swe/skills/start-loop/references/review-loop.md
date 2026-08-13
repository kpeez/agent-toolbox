# Review loop — why the constants are what they are

The run procedure fixes one assembled review, a different model family, and at
most two fix rounds. Those numbers come from measured failure modes of
agent-review loops, not taste.

## One fresh reviewer, different family

A model reviewing its own output is biased toward it, and intrinsic
self-correction without external feedback measurably fails or backfires — the
implementer is never its own reviewer. A reviewer from the implementer's model
family inherits its blind spots; a different family breaks the correlation.

## Gates green is the entry condition

Review starts only after lint, types, and tests pass on the assembled branch.
A review of failing code is a rubber stamp, and a reviewer that approves while
tests fail is a broken verifier — a measured failure mode that manufactures
confidence and is worse than no check. Fix the gate or the reviewer before
trusting either.

## Ground every finding in the spec

The reviewer receives the spec text and the assembled diff, and each finding
must cite the spec clause or failing check it violates. Spec-grounded review
roughly doubles the rate at which findings are worth acting on compared to
free-form judgment. Expect roughly 4 in 10 findings to be actionable even so —
act on correctness and requirement gaps; style opinions are optional and
chasing them is churn, not quality.

## Elicit defects, decide in code

Never ask the reviewer to approve, reject, or judge "good enough" — cost and
framing language in a review prompt shifts reported failure estimates by
double-digit points. The reviewer returns a neutral defect list against the
criteria; the lead applies the accept threshold itself, deterministically.

## Redact metadata

The reviewer sees the diff and the spec — not PR titles, descriptions,
commit-message claims, or anything asserting the code is tested or bug-free.
Such claims measurably distort defect detection, and stripping them restores
it. The reviewer body's contract mirrors this: judge the code, ignore the
claims.

## Two fix rounds, then escalate

Most real fixes land in the first round; iteration chains that run to ~10
rounds are net-negative, degrading nearly half the time. After the second fix
round, remaining findings escalate to the user rather than looping. Stop
signal for re-review: no new cited findings and no test changes — further
rounds are rubber-stamping.

## Keep the spec verbatim between rounds

Fix-round dispatches carry the original spec text and the reviewer's cited
findings — never a paraphrase of either. Each rephrasing hop accumulates
distortion, and spec drift across refinement rounds is a measured effect.
