---
name: implement
description: "Implement an authorized feature or fix through relevant verification. Use for scoped code changes; not for specs, tracker publication, or PR delivery."
---

# Implement

Implement one authorized, scoped task through proportionate evidence and
verification. Read the task and relevant current state before acting. Preserve
unrelated work and the user's authority boundaries. This skill's job is the
smallest justified code change with evidence.

## Contract

1. Make the smallest justified change. Challenge the result against the
   intended outcome and remove unnecessary code, abstractions, or special cases.
   A no-change result is valid when the requested behavior already holds.
2. Choose evidence by behavioral risk. Use `/testing-code` only when test
   design, an uncertain behavior, or an explicit probe warrants it; otherwise a
   static check, reproducible demonstration, existing workflow, or explicit
   no-permanent-test decision may be enough.
3. Run relevant repository gates and behavior-specific checks. A failing
   required gate blocks completion and publication, but continue authorized
   diagnosis and correction when that can resolve the failure. Report unrelated
   baseline failures without silently fixing unrelated code.
4. Report the change, evidence, verification, and unresolved concerns.

## Tracked work checklist

- Confirm the approved revision and explicit scope using the selected tracker
  route's approval mechanism. Treat Todo status as readiness, separately from
  execution permission.
- Respect holds, dependencies, and one supervised owner; check the fresh
  checkout, PRs, and jobs before editing.
- For configured Linear work, record `start`, `progress`, `handoff`, `review`, and `evidence` notes via
  `record` during the work, not as a separate ritual (see
  [operations](../to-issues/references/workflow-operations.md)).
- Put handoff in the selected tracker issue (privately for Linear): state, verified evidence, next
  action, worktree and uncommitted work, jobs, and what not to repeat.
- Get independent review for substantive changes; no PR, draft, or merge marks
  Done automatically.

`/execute-spec` coordinates a full approved spec run. A standalone developer
may delegate bounded work when useful and remains responsible for decisions,
review, and final verification. A bounded worker reports to its caller and does
not create an uncontrolled delegation chain.
