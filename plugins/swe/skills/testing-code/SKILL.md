---
name: testing-code
description: "Design behavioral tests or disposable probes for uncertain code. Use for testing strategy, regression coverage, TDD, or spikes."
---

# Behavioral testing

Use scratch probes to learn, then retain only the smallest stable evidence that
uniquely protects meaningful behavior. Tests are not required for every change:
the evidence may be a committed test, shared workflow, static check,
reproducible demonstration, or explicit no-permanent-test decision. There is no
red/green choreography, test-per-goal rule, coverage quota, or mutation-score
target.

## Contract

Test public behavior and independently justified oracles, not source structure.
Work through one behavioral risk or equivalence class at a time. Before choosing
an evidence mode, name the promised behavior or invariant, the independent
oracle, and the narrowest stable public seam. If any remain unclear, explore
before committing a test.

## Probe when useful

Use a safe available scratch location, such as `artifacts/temp/`, when the
behavior, interface, or oracle is uncertain. Do not require an ignore-file edit
just to run a probe. Exercise real imports, types, and call sites. Give the
probe one command, a meaningful exit status, and enough output to distinguish
the result. Delete task-owned probes after they become stable evidence or their
verdict is recorded; do not remove unrelated shared artifacts.

## Choose and settle evidence

Choose the smallest evidence mode that distinguishes the risk: a regression,
property or state invariant, representative boundary workflow, targeted
mutation audit, disposable probe, static check, or an explicit no-permanent-test
decision. Read [references/tests.md](references/tests.md) when choosing
permanent evidence, property tests, mutation audits, or representative
workflows; it contains the admission gate and technique guidance.

When evidence crosses a dependency boundary, prefer a small faithful real
substitute before a mock. Read [references/mocking.md](references/mocking.md)
when choosing a substitute or mock, especially for ML and external services.

Before completion, tie each observable claim to its oracle and evidence mode,
remove task-owned scratch work, and run direct and behavior-specific checks. A
failing required gate blocks completion; investigate an in-scope failure before
claiming success and report unrelated baseline failures. Record a verdict-only
probe or durable decision only when it affects future work and the established
project workflow calls for a record.

## Avoid mock-slop

Test outcomes at stable public boundaries. Internal call counts, private methods,
mock interactions, framework behavior, and duplicate wiring checks are signals
to inspect, not automatic tests or deletion targets. Mock only true external
boundaries; use real code or faithful local substitutes for dependencies you
control. At service or message boundaries, exercise the consumer's real client
and assert only facts that matter to that consumer.

For a long-running autonomous exploration with a metric target and many
experiments, use `lab:autoresearch`. A scratch probe answers a bounded question
in one sitting.
