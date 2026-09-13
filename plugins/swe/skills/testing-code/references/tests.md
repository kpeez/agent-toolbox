# Choosing Behavioral Evidence

Read this reference when deciding whether a permanent test is worth its
maintenance cost. Keep only the smallest stable sensor for meaningful public
behavior, an actual regression, or a high-risk invariant.

## Admission gate

Before committing a test, answer all five:

1. **Behavior:** What caller-visible promise, observed defect, or high-risk
   invariant does it protect?
2. **Oracle:** How is the expected result known independently of production
   logic and incidental structure?
3. **Uniqueness:** What plausible failure escapes the existing suite, type
   checker, linter, assertions, and shared workflows?
4. **Seam:** What narrow stable public boundary exposes the behavior?
5. **Cost:** Is the sensor deterministic, legible, and proportionate to the
   protected risk?

If the gate does not hold, use a disposable probe, reproducible demonstration,
static or type check, assertion, or explicit no-permanent-test decision. There
is no quota. A silent calculation error may merit a test; a loud but duplicate
sensor may not.

## Choose evidence

Choose a suitable mode rather than following a fixed sequence:

- **Actual defect:** one deterministic regression at the public seam, using the
  captured offending payload where a boundary or parser is involved.
- **Broad invariant or state transition:** one property or stateful test for the
  equivalence class. Read [property-testing.md](property-testing.md) when this
  is the right shape.
- **Public system boundary:** one representative integration or contract
  workflow using the real client where practical. Read
  [behavior-patterns.md](behavior-patterns.md) for concrete oracle patterns.
- **Uncertain changed core logic:** a targeted mutation audit, only to find a
  credible surviving product fault. Read [mutation-audits.md](mutation-audits.md)
  when this applies.
- **None:** no permanent test. Keep the probe or other proportionate evidence.

A metamorphic relation or trusted simpler model can supply an oracle when its
relation is known independently. Do not use one when it merely seems plausible
or shares production assumptions.

## Avoid test theater

Do not add tests for implementation-method parity, private methods, mock call
order, framework behavior, constants, registries, validation branches, wiring,
every permutation of one equivalence class, non-crash checks when a value or
invariant oracle exists, broad snapshots, behavior already protected by a
cheaper sensor, or coverage improvement by itself.

Remove redundant examples only after a clearer property or representative
workflow demonstrably preserves their distinct useful coverage. Good tests
assert caller-relevant values or invariants at stable public seams, run without
network or cache state, and fail for one credible product reason.
