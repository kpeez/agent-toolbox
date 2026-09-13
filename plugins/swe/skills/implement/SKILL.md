---
name: implement
description: "Implement an authorized feature or fix through relevant verification. Use for scoped code changes."
---

# Implement

Implement one authorized, scoped task through proportionate evidence and
verification. Read the task and relevant current state before acting. Preserve
unrelated work and the user's authority boundaries.

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
4. Report the change, evidence, verification, and unresolved concerns. For
   tracked work, record only useful transition state: resume action, ruled-out
   approach, gotcha, stale-spec correction, or in-flight uncommitted work.

`/execute-spec` coordinates a full approved spec run. A standalone developer
may delegate bounded work when useful and remains responsible for decisions,
review, and final verification. A bounded worker reports to its caller and does
not create an uncontrolled delegation chain. If local CLI delegation to an
external provider is explicitly authorized, follow `/external-subagents`.
