---
name: implement
description: "How to implement a spec or feature: prove behavior before committing to it. Use whenever implementing a feature, bugfix, or behavior change."
---

# Implement

One implementation discipline for a developer or bounded worker doing one task.

## Prove behavior before you commit to it

**`/testing-code`** is the behavioral verification discipline. Tests are not a required
output of every change: use disposable `artifacts/temp/` probes when useful, then
retain only the smallest stable sensor for meaningful public behavior, an actual
regression, or a high-risk invariant. Choose evidence by behavioral risk,
independent oracle, uniqueness, stable public seam, and proportional cost. One
property or representative workflow may protect several claims; a static check,
reproducible demonstration, or explicit no-permanent-test decision may be the
right evidence for another. Record a verdict-only probe when its result affects
a durable decision or future resumption. If you catch yourself calling a
promised behavior done with no evidence, stop and produce it; a failing required
test, type check, or lint gate is a stop, not a warning to continue past.

`/execute-spec` coordinates a full spec run. A standalone developer may delegate
bounded exploration or implementation when useful and remains responsible for
decisions, review, and final verification. A bounded worker reports to its
caller and does not create an uncontrolled delegation chain. If local CLI
delegation to an external provider is explicitly authorized, follow
`/external-subagents`'s contract.

## Implement one task

The discipline an implementer agent, or a developer working a single issue
directly, follows for one task.

1. Read the assigned task or issue and its relevant current state before acting.
2. Prove behavior per `/testing-code`, working through one behavioral risk or equivalence
   class at a time and probing in `artifacts/temp/` when the design is uncertain.
3. Once the intended behavior works, challenge the implementation against the
   intended outcome. Delete unnecessary code, abstractions, and special cases
   based on weak assumptions. Simplify what remains. Make only justified
   reductions within scope, and preserve meaningful behavioral coverage and
   unrelated work. Prefer deleting over simplifying, simplifying over
   optimizing, and optimizing over automating. No change is a valid result.
4. Run the repository's available verification gates and behavior-specific
   checks on the resulting implementation. A failure at any required gate
   stops the task; it is not a warning to note and continue past.
5. Follow the caller's tracker-update contract when one exists. Record only
   information needed to resume or understand a meaningful transition:
   - **Resume** - the concrete next action.
   - **Ruled out** - approaches tried and abandoned, and why.
   - **Gotcha** - non-obvious constraints discovered the hard way.
   - **Correction** - where the spec or issue body is stale.
   - **In flight** - work started but not committed, and its state.
6. Report results, verification, and unresolved concerns to whoever
   orchestrates you. A bounded worker sends questions to its caller. A
   standalone developer may interact with the user directly.

## Cross-references

- `/sharpen` - stress-test a plan before writing tests or scratch scripts.
- `/write-spec new <name>` - scaffold a pure-markdown spec whose Verification
  section names observable claims, oracles, and acceptable evidence modes.
