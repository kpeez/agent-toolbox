# Choosing Behavioral Evidence

Permanent tests are sensors with maintenance cost, not required artifacts. Keep
only the smallest stable sensor for meaningful public behavior, an actual
regression, or a high-risk invariant.

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

Do not reduce this to silent versus loud. Wrong calculations and broken
invariants are often silent, but a loud regression can still merit a permanent
test when it is important, recurring, costly, or safety-relevant. Conversely, a
silent case does not earn a test when its oracle mirrors production or another
sensor already protects it.

If the gate does not hold, use a disposable probe, reproducible demonstration,
static check, type check, assertion, or explicit no-permanent-test decision.
There is no quota.

## Technique ladder

Choose the first applicable evidence:

1. **Real reported defect:** one deterministic regression at the public seam.
2. **Broad independent invariant:** one property test for the equivalence class.
3. **Sequences or transitions:** one small stateful or model property.
4. **Public system boundary:** one representative integration or contract
   workflow, using the real client where practical.
5. **Uncertain changed core logic:** a targeted mutation audit; strengthen the
   suite only for a credible surviving product fault.
6. **None:** no permanent test.

Conditional tools also fit when justified: a metamorphic relation can supply an
oracle when transformations have known relations, and a trusted simpler model
can supply a differential oracle. Do not use either when the relation is merely
plausible or the reference shares production code or assumptions.

## Property-based testing

Property testing is valuable when many domain values share an invariant that can
be stated without reading the implementation. Useful shapes include:

- round trips: decoding an encoding returns the normalized original;
- idempotence: normalizing twice equals normalizing once;
- conservation: totals, membership, or mass are not created or lost;
- monotonicity and bounds: changed inputs preserve promised order or range;
- permutation invariance: irrelevant ordering does not change the result;
- model equivalence: production agrees with a smaller independently trusted
  reference; and
- state invariants: generated action sequences preserve public rules.

Rules:

- Write the invariant in plain language first. If it is unclear, do not use
  property testing.
- Generate domain-valid values and meaningful invalid classes, not arbitrary
  noise for case count.
- Use one property per distinct invariant. Add another only for a different
  failure class.
- Never derive expected values by calling, copying, or algebraically restating
  production logic.
- Treat a minimized counterexample as diagnostic evidence. Add a fixed example
  only when that concrete case communicates lasting regression meaning beyond
  the property.
- Delete table-driven or fixed examples that the property fully subsumes.

Do not use property testing for getters, constructors, framework behavior,
ordinary wiring, a handful of discrete business examples, or domains whose
generator is harder to understand than the implementation.

## Mutation audits

Mutation asks whether existing evidence notices a plausible mistake. Use it
occasionally for changed or high-risk core logic such as parsers, calculations,
authorization, normalization, branching business rules, or state transitions.
It is not a routine release gate.

Rules:

- Scope the audit to changed or high-risk core logic, never the whole repository.
- Sample a few plausible faults: inverted comparisons, off-by-one boundaries,
  omitted branches, swapped arithmetic operators, removed normalization, or an
  invalid state transition.
- A surviving mutant earns a stronger behavioral test only when it represents a
  credible product bug.
- Record equivalent, impossible, or irrelevant mutants and move on. Do not add
  theater just to kill them.
- Do not target a score, add routine whole-repository mutation CI, or use line
  coverage as a proxy for mutant quality.
- Manual mutation is acceptable: make one or two plausible changes, confirm the
  relevant sensor fails, then restore production. The information matters, not
  the framework.

## High-value patterns

### Independent calculation oracle

Compare optimized behavior with a small readable reference that shares no
implementation:

```python
def test_chunked_attention_matches_naive():
    q, k, v = (torch.randn(2, 8, 64, 32, generator=gen) for _ in range(3))
    expected = naive_attention(q, k, v)
    actual = chunked_attention(q, k, v, chunk_size=16)
    torch.testing.assert_close(actual, expected, rtol=1e-4, atol=1e-5)
```

### Behavioral invariant

Assert a relation the domain demands rather than a sampled output:

```python
def test_future_frames_cannot_affect_past_logits():
    frames = torch.randn(1, 16, 3, 224, 224)
    past = model(frames).logits[:, :8]
    frames[:, 8:] = torch.randn_like(frames[:, 8:])
    torch.testing.assert_close(model(frames).logits[:, :8], past)
```

### Representative workflow

Drive the assembled system through its public entry point with real
collaborators. One workflow can protect several claims. Add another only for a
genuinely different risk, not another permutation of the same path.

## Test theater

Do not add tests for:

- implementation-method parity, private methods, or mock call order;
- framework or library behavior;
- constants, registries, validation branches, or wiring restated from source;
- every permutation of one equivalence class;
- shape or non-crash checks when a value or invariant oracle exists;
- exact snapshots broader than the consumer contract;
- behavior already protected by a cheaper or shared sensor; or
- coverage improvement by itself.

Delete redundant examples when a clearer property or representative workflow
protects the same behavior. Good tests assert caller-relevant values or
invariants at public seams, run deterministically without network or cache
state, and fail for one credible product reason.
