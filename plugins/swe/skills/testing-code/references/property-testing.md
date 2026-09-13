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
- state invariants: generated action sequences preserve public rules.

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

Do not use property testing for getters, constructors, framework behavior,
ordinary wiring, a handful of discrete business examples, or domains whose
generator is harder to understand than the implementation.
