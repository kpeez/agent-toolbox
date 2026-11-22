# Property-based testing

Read this reference when many domain values share a broad invariant or when
generated action sequences expose state rules. Property testing is useful only
when the invariant and a domain-valid generator are easier to explain than the
implementation.

In Python, [Hypothesis](https://hypothesis.readthedocs.io/) provides shrinking
and stateful testing. Useful independent relations include:

- round trips: decoding an encoding returns the normalized original;
- idempotence: normalizing twice equals normalizing once;
- conservation: totals, membership, or mass are not created or lost;
- monotonicity and bounds: changed inputs preserve promised order or range;
- permutation invariance: irrelevant ordering does not change the result;
- model equivalence: production agrees with a smaller independently trusted
  reference; and
- state invariants: generated action sequences preserve public rules;
- inverse pairs: `decompress(compress(x)) == x`;
- cheap checks of costly work: `is_sorted(sort(xs))`; and
- algebra: commutativity `f(a, b) == f(b, a)`, associativity, and an
  identity element `f(x, e) == x` for combining operations.

Assert the strongest relation the code supports. From weakest to strongest:
no crash, then type preserved, then an invariant, then idempotence, then a
round trip or model equivalence. A property that only shows "no crash"
rarely pays for itself. First look for a small refactor that exposes a
stronger relation, such as a pure calculation pulled out of I/O. If none
exists, use example tests and say so.

The shape in code is one invariant, a domain-valid generator, and no expected
value computed from production:

```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_normalize_is_idempotent(xs):
    once = normalize(xs)
    assert normalize(once) == once
```

Rules:

- State the invariant in plain language first. If it is unclear, do not use
  property testing.
- Generate domain-valid values and meaningful invalid classes, not arbitrary
  noise for case count.
- Use one property per distinct invariant. Add another only for a different
  failure class.
- Never derive expected values by calling, copying, or algebraically restating
  production logic.
- Treat a minimized counterexample as diagnostic evidence. Add a fixed example
  only when it communicates lasting regression meaning beyond the property;
  Hypothesis's `@example(...)` decorator keeps it attached to that property.
- Remove a table-driven example only after confirming that the property
  preserves its useful, distinct coverage.

Two ways a property asserts nothing:

- **Tautology.** `assert add(a, b) == a + b` restates the implementation, so
  a bug both share cannot fail it. One exception: `f(x) == f(x)` is a real
  determinism check when `f` may not be pure, such as a serializer over a
  set, a hash, or code that reads the clock.
- **Vacuity.** An `assume()` that rejects almost every input exercises
  nothing, and contradictory filters run zero cases and still pass. Build
  the constraint into the generator instead.

Do not use property testing for getters, constructors, framework behavior,
ordinary wiring, a handful of discrete business examples, or domains whose
generator is harder to understand than the implementation.
