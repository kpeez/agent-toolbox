---
name: testing-code
description: "Gate, design, and audit tests. Use before adding or rewriting any permanent test, for probes, TDD, regression coverage, testing strategy, and judging a diff's tests. Also for reviewing or pruning existing test suites."
---

# Testing code

One skill owns all work on tests. Pick the mode from the request:

- **New tests and probes:** adding, rewriting, or judging a test, a probe, TDD,
  regression coverage, or testing strategy. Follow the rest of this file down to
  the autoresearch pointer. This mode has no numbered procedure; its section
  headings are its steps.
- **Audit:** reviewing or pruning existing tests, a test-suite sweep, or a
  pruning campaign. Follow "Audit mode" at the end of this file.

Both modes share one value bar: [references/test-value.md](references/test-value.md).

## New tests and probes

Default to no new permanent test. A test is a maintenance cost that must be
repaid by protecting behavior nothing cheaper already protects. Use scratch
probes to learn, then retain only the smallest stable evidence that uniquely
protects meaningful behavior: a committed test, shared workflow, static check,
reproducible demonstration, or explicit no-permanent-test decision. A TDD
request goes through the admission gate below; there is no red-green ritual,
test-per-goal rule, coverage quota, or suite-wide mutation-score target, but
every new or rewritten permanent test must have been seen failing, often
through one deliberate mutation.
Keeping an existing valuable test during an audit does not itself require a
new mutation exercise.

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
consolidate them in the same change. Use audit mode for broader pruning.
During implementation, never delete, skip, or loosen an existing test to get
green; if a test looks wrong, report it with evidence.

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
  demonstration's verdict or reproducible command as evidence. Retain a probe
  file only when it is an intentional durable artifact; otherwise remove it as
  described above.

A metamorphic relation or trusted simpler model can supply an oracle when its
relation is known independently. Do not use one that merely seems plausible or
shares production assumptions.

When evidence crosses a dependency boundary, prefer a small faithful real
substitute before a mock. Read [references/mocking.md](references/mocking.md)
when choosing a substitute or mock, especially for ML and external services.

Before completion, tie each observable claim to its oracle and evidence mode,
remove task-owned scratch work, and run direct and behavior-specific checks. A
failing required gate blocks completion; investigate an in-scope failure before
claiming success, and handle an unrelated baseline failure per
[ancillary-fixes](../principle-ancillary-fixes/SKILL.md). For each permanent
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

## Audit mode

Shrink an existing suite to the tests that earn their cost. A test added or
rewritten during an audit passes the admission gate above. Read
[references/audit.md](references/audit.md) for the detail of each step. For a
whole subsystem, read [references/campaign.md](references/campaign.md) first.

1. `1-record-suite-baseline`: Before any edit, record each in-scope test's
   pass state and the test line counts at the starting commit. Keep baseline
   failures in their own list.
2. `2-mark-candidates`: Read each candidate and its production owner in full.
   Mark it `retain`, `repair`, `consolidate`, or `delete` with its evidence
   fields. A candidate with a missing field is not ready.
3. `3-edit-in-small-batches`: Edit one coherent owner-boundary batch. Delete
   the test-only seams the removed tests kept alive. Rerun the owner and sibling
   tests after each batch. Sequence the batches as in
   [principle-sequence-verifiable-units](../principle-sequence-verifiable-units/SKILL.md).
4. `4-mutate-changed-contracts`: Mutate the production owner of each
   `consolidate` or `repair` contract once. Confirm its keeper fails. Restore
   the source byte for byte. Then run the
   [validation checks](references/audit.md#validation-checks), including the
   repository's required gates.
5. `5-independent-preservation-review`: Get a review of the final diff from
   an agent that did not edit, such as the swe reviewer agent. Report an
   unavailable review as a verification gap.
6. `6-publish-draft-pr`: When publication is authorized, push the final
   commits and update the draft PR with [ship-pr](../ship-pr/SKILL.md).
   Otherwise report the reviewed local diff.

Reply with the tests and production lines removed, the contracts kept, and the
review result. The full handoff list is in
[references/audit.md](references/audit.md#handoff).
