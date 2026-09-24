---
name: testing-code
description: "Gate and design new behavioral tests or disposable probes. Use before adding or rewriting any permanent test, when judging a diff's new tests, and for testing strategy, regression coverage, TDD, or spikes. Not for pruning existing suites."
---

# Behavioral testing

Default to no new permanent test. A test is a maintenance cost that must be
repaid by protecting behavior nothing cheaper already protects. Use scratch
probes to learn, then retain only the smallest stable evidence that uniquely
protects meaningful behavior: a committed test, shared workflow, static check,
reproducible demonstration, or explicit no-permanent-test decision. There is
no TDD ritual, test-per-goal rule, coverage quota, or suite-wide
mutation-score target, but every retained test must have been seen failing,
often through one deliberate mutation.

## Contract

Test public behavior and independently justified oracles, not source structure.
Work through one behavioral risk or equivalence class at a time. Before choosing
an evidence mode, name the promised behavior or invariant, the independent
oracle, and the narrowest stable public seam. If any remain unclear, explore
with a probe before writing a test.

## Admission gate

Before adding or rewriting a permanent test, answer all six. A missing or weak
answer means do not add it.

1. **Behavior:** What caller-visible promise, observed defect, or high-risk
   invariant does it protect?
2. **Failure:** What credible regression turns it red? Name the bug, not the
   line it touches.
3. **Oracle:** How is the expected result known independently of production
   logic and incidental structure?
4. **Owner:** Why does existing coverage (the suite, type checker, linter,
   assertions, and shared workflows) not already catch that failure? Each
   contract has one primary test at the strongest boundary; another layer needs
   its own risk, such as a transport or lifecycle failure the owner cannot
   reach. Extend an existing table case or fixture rather than adding a
   near-duplicate.
5. **Seam:** Does it run through a stable public boundary that production
   callers also use? If it needs an export, flag, wrapper, or injection hook
   that only tests use, move the test to the real boundary instead.
6. **Cost:** Is it deterministic, offline, legible, and proportionate to the
   protected risk?

Then check the test against the junk patterns in
[references/test-value.md](references/test-value.md). A match fails the gate
unless that file's retention bar names the contract the test independently
guards. A test that would break under a behavior-preserving refactor asserts
implementation; rewrite it at the owning boundary or drop it.

**Seen red.** Watch the test fail for the intended reason before retaining it.
A regression test must fail on the pre-fix code. A test of new or existing
behavior must fail under one deliberate mutation of its production owner;
restore the source byte for byte afterward. A test never seen failing proves
the fixture, not the behavior. One regression at the owner boundary covers a
bug; do not replay the same scenario at every layer it crosses.

When a change makes existing tests obsolete or duplicative, delete or
consolidate them in the same change. Use `/test-audit` for broader pruning.

## Probe when useful

Use a safe available scratch location, such as `artifacts/temp/`, when the
behavior, interface, or oracle is uncertain. Do not require an ignore-file edit
just to run a probe. Exercise real imports, types, and call sites. Give the
probe one command, a meaningful exit status, and enough output to distinguish
the result. Delete task-owned probes after they become stable evidence or their
verdict is recorded; do not remove unrelated shared artifacts.

## Choose and settle evidence

Choose the smallest mode that distinguishes the risk:

- **Actual defect:** one deterministic regression at the public seam, using the
  captured offending payload where a boundary or parser is involved.
- **Broad invariant or state transition:** one property or stateful test for
  the equivalence class. Read
  [references/property-testing.md](references/property-testing.md).
- **Public system boundary:** one representative integration or contract
  workflow using the real client where practical. Read
  [references/behavior-patterns.md](references/behavior-patterns.md) for oracle
  patterns.
- **Uncertain changed core logic:** a targeted mutation audit, only to find a
  credible surviving product fault. Read
  [references/mutation-audits.md](references/mutation-audits.md).
- **None:** no permanent test. Keep the probe, static check, or reproducible
  demonstration as evidence.

A metamorphic relation or trusted simpler model can supply an oracle when its
relation is known independently. Do not use one that merely seems plausible or
shares production assumptions.

When evidence crosses a dependency boundary, prefer a small faithful real
substitute before a mock. Read [references/mocking.md](references/mocking.md)
when choosing a substitute or mock, especially for ML and external services.

Before completion, tie each observable claim to its oracle and evidence mode,
remove task-owned scratch work, and run direct and behavior-specific checks. A
failing required gate blocks completion; investigate an in-scope failure before
claiming success and report unrelated baseline failures. For each permanent
test added or rewritten, report the contract it guards and how it was seen red.
Record a verdict-only probe or durable decision only when it affects future
work and the established project workflow calls for a record.

## Avoid mock-slop

Test outcomes at stable public boundaries. Internal call counts, private
methods, mock interactions, framework behavior, and duplicate wiring checks
rarely pass the gate as new tests; in existing suites they are audit
candidates, not automatic deletions. Mock only true external boundaries; use
real code or faithful local substitutes for dependencies you control. At
service or message boundaries, exercise the consumer's real client and assert
only facts that matter to that consumer.

For a long-running autonomous exploration with a metric target and many
experiments, use `lab:autoresearch`. A scratch probe answers a bounded question
in one sitting.
