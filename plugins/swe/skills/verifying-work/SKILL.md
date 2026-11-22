---
name: verifying-work
description: "Choose the strongest check that proves a change: a model check, types, a lint rule, an end-to-end check, a property test, or a unit test. Use before you add or rewrite a permanent test, for a failing check before a fix, for probes and regression evidence, and to judge a diff's tests."
argument-hint: "[change, diff, or behavior]"
---

# Verifying work

Plan a change as types, inputs, and outputs, and the behavior the system
shows its users. Then prove that behavior with the strongest check that
settles the risk.

## Steps

1. `1-name-the-behavior`: Name the types, the inputs and outputs, the
   behavior users observe, an independent oracle, and the narrowest stable
   public seam. Probe first when any is unclear.
2. `2-choose-the-rung`: Take the first rung in [Rungs](#rungs) that settles
   the risk. The check can be a one-off command that leaves nothing in the
   repository.
3. `3-pass-the-admission-gate`: Before you keep a test or check in the
   repository, answer all six questions in
   [Admission gate](#admission-gate). A missing or weak answer means you do
   not keep it.
4. `4-see-it-fail`: Watch each new or rewritten check fail for the intended
   reason, on the pre-fix code for a regression.
5. `5-clean-up-and-report`: Remove task-owned scratch work. Report each
   claim with its rung, the command you ran, and the result you saw. For each
   kept check, report the contract it guards and how you saw it fail.

## Rungs

A higher rung makes a class of bugs impossible, or covers every case in a
stated scope. A lower rung covers only the cases someone wrote.

1. **Model check.** A state machine, event order, retries, or concurrency.
   Run the project's formal verification skill when one exists. When the
   change adds or changes a state machine and the project has none, suggest
   `create-formal-verification-skill` to the user.
2. **Types.** Make the wrong state unrepresentable, so the compiler rejects
   the bug. Follow
   [type-system-discipline](../principle-type-system-discipline/SKILL.md).
3. **Lint.** A bad pattern that still builds. Add a rule to the linter that
   the repository already runs, as step `lint-or-check` of
   [correct](../correct/SKILL.md) says.
4. **End-to-end.** Drive the system through its real entry point, such as a
   CLI, an HTTP endpoint, a UI, or a hook, and observe the result. Use the
   project's verification skill when one exists;
   [verification-skill](../verification-skill/SKILL.md) builds one. For a
   running service, read
   [references/live-service-checks.md](references/live-service-checks.md).
5. **Property test.** An invariant, a round trip, idempotence, or
   equivalence over a domain of inputs. Read
   [references/property-testing.md](references/property-testing.md).
6. **Unit test.** Valid, but often the weakest evidence: it shows what one
   piece does, not what the system does. Use it when no higher rung fits, or
   a higher one costs much more. Drive it through the seam that callers use,
   as
   [test-behavior-not-implementation](../principle-test-behavior-not-implementation/SKILL.md)
   says.

## Contract

Test public behavior against an independently justified oracle, not source
structure. Work through one behavioral risk or equivalence class at a time.
Drive the subject through its users' interface with one concrete input, and
derive the expected value from the requirement. Keep a check that fails when
the behavior breaks and passes when only the internals change. Rewrite or
delete the rest.

## Admission gate

Default to no new permanent test. A kept test is a maintenance cost that must
protect behavior nothing cheaper already protects. Before you add or rewrite
a permanent test or check, answer all six:

1. **Behavior:** What caller-visible promise, observed defect, or high-risk
   invariant does it protect?
2. **Failure:** What credible regression turns it red? Name the bug, not the
   line it touches.
3. **Oracle:** How is the expected result known independently of production
   logic and incidental structure?
4. **Owner:** Why does existing coverage (the suite, type checker, linter,
   assertions, and shared workflows) not already catch that failure? Each
   contract has one primary check at the strongest boundary; another layer
   needs its own risk, such as a transport or lifecycle failure the owner
   cannot reach. Extend an existing table case or fixture rather than adding
   a near-duplicate.
5. **Seam:** Does it run through a stable public boundary that production
   callers also use? If it needs an export, flag, wrapper, or injection hook
   that only tests use, move it to the real boundary instead.
6. **Cost:** Is it deterministic, offline, legible, and proportionate to the
   protected risk?

Then check it against the junk patterns in
[references/test-value.md](references/test-value.md). A match fails the gate
unless that file's retention bar names the contract the check independently
guards.

**Seen red.** A regression check must fail on the pre-fix code. A check of
new or existing behavior must fail under one deliberate mutation of its
production owner; restore the source byte for byte afterward. A check never
seen failing proves the fixture, not the behavior. One regression at the
owner boundary covers a bug; do not replay the same scenario at every layer
it crosses.

When a change makes existing tests obsolete or duplicative, delete or
consolidate them in the same change. During implementation, never delete,
skip, loosen, or special-case a test or a check to get green.
Special-casing includes hard-coding the expected output and detecting that a
test is running. If a test looks wrong, report it with evidence.

## Failing check first

Use this cadence when the user asks for TDD, a failing test, or a regression
test, or when a cheap check reproduces the bug. Skip it when no such check is
clear and nobody asked for one.

1. Understand the bug. Name the intended behavior, the current behavior, the
   affected path, and the smallest observable reproduction.
2. Choose the highest rung that reproduces the bug: a type or lint rule that
   rejects it, an end-to-end check through the entry point, a property that
   finds the counterexample, or a unit test at the public seam. Reuse a check
   that the codebase already runs where one fits.
3. Write the smallest check that would have caught the bug. It encodes the
   intended behavior, not the current implementation.
4. Run it before the fix. Confirm it fails for the intended reason. If it
   passes, or fails for an unrelated reason, correct the check or the
   reproduction before you edit production code.
5. Make the smallest production change that gives the intended behavior and
   keeps nearby contracts.
6. Run the check again. Confirm it passes.

- Change a check only when the expected behavior changed. Never change it to
  match a wrong implementation.
- Keep the regression check on the bug. Avoid broad fixture churn and
  unrelated coverage.
- For a flaky bug, make the check deterministic where possible and write down
  the signal it locks down.
- When the bug exposes a broader class of failures, land the focused
  regression first. Then consider a higher rung for the class.

Report the failing-before check and the failure it produced, and the
passing-after run. If you could not show the failure before the fix, say why
and name the closest check you used instead.

## Probe when useful

Use `.agents/scratch/<branch-slug>/` ([agent scratch](../../references/agent-scratch.md))
when the behavior, interface, or oracle is uncertain. Exercise real imports,
types, and call sites. Give the probe one command, a meaningful exit status,
and enough output to distinguish the result. Delete task-owned probes after
they become stable evidence or their verdict is recorded; do not remove
unrelated shared artifacts.

For a long exploration with a metric target and many attempts, use the
`hillclimb-metric` playbook of the `swe-mode` router. A probe answers a
bounded question in one sitting.

## Settle the evidence

A metamorphic relation or trusted simpler model can supply an oracle when its
relation is known independently. Do not use one that merely seems plausible
or shares production assumptions.

When evidence crosses a dependency boundary, prefer a small faithful real
substitute before a mock. Read [references/mocking.md](references/mocking.md)
when you choose a substitute or mock, especially for ML and external
services. Mock only true external boundaries. Internal call counts, private
methods, and mock interactions rarely pass the gate. At a service or message
boundary, exercise the consumer's real client and assert only facts that
matter to that consumer. For oracle patterns at a system boundary, read
[references/behavior-patterns.md](references/behavior-patterns.md).

When changed core logic may have weak evidence, read
[references/mutation-audits.md](references/mutation-audits.md).

Before completion, tie each observable claim to its rung and oracle, remove
task-owned scratch work, and run direct and behavior-specific checks. A
failing required gate blocks completion; investigate an in-scope failure
before claiming success, and handle an unrelated baseline failure per
[ancillary-fixes](../principle-ancillary-fixes/SKILL.md).

## Existing suites

To find flaws in an existing test suite, such as missed states, tests that
check implementation, or checks on a lower rung than the risk needs, use
[test-audit](../test-audit/SKILL.md).
