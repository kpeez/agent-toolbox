# What to Test — and What Not To

The test for a test: **what silent bug does it catch?** A bug is _silent_ if the
pipeline runs to completion and produces wrong numbers, leaked data, or broken
invariants. A bug is _loud_ if the first real run throws a traceback that any
agent fixes in one step. Tests exist to catch silent bugs. Loud bugs are already
covered — by the interpreter, the import system, and the first smoke run.

## Worth writing

**Parity with a reference implementation.** The optimized path must match the
naive path you can read and trust — the single highest-value test in numerical
code. Catches chunking, masking, and broadcasting bugs that produce
plausible-but-wrong numbers.

```python
def test_chunked_attention_matches_naive():
    q, k, v = (torch.randn(2, 8, 64, 32, generator=gen) for _ in range(3))
    naive = naive_attention(q, k, v)          # readable einsum, O(n^2) memory
    chunked = chunked_attention(q, k, v, chunk_size=16)
    torch.testing.assert_close(chunked, naive, rtol=1e-4, atol=1e-5)
```

**Invariants the math demands.** Causality, masking, permutation invariance,
equivariance. These break silently — the model still trains, just on leaked
information.

```python
def test_future_frames_cannot_affect_past_logits():
    frames = torch.randn(1, 16, 3, 224, 224)
    past = model(frames).logits[:, :8]
    frames[:, 8:] = torch.randn_like(frames[:, 8:])  # perturb the future
    torch.testing.assert_close(model(frames).logits[:, :8], past)
```

**Gradient flow and freezing.** A frozen backbone that isn't frozen, or an
adapter that never receives gradient, trains for days before anyone notices.

```python
def test_lora_finetune_updates_only_adapter_weights():
    model(batch).loss.backward()
    for name, p in model.named_parameters():
        if "lora_" in name:
            assert p.grad is not None and p.grad.abs().sum() > 0, name
        else:
            assert p.grad is None, f"frozen param received grad: {name}"
```

**Data integrity.** Split leakage and misalignment inflate every downstream
metric. Same idea for alignment: a synthetic video where frame `i` has pixel
value `i` proves sampled timestamps index the frames they claim.

```python
def test_splits_share_no_subjects():
    train, val = make_splits(manifest, seed=0)
    assert {c.subject_id for c in train}.isdisjoint(c.subject_id for c in val)
```

**Round-trips.** Checkpoint save/load must reproduce outputs exactly. Parsers
are tested against **captured real model outputs** — every parser bugfix adds
the offending output as a fixture first (red), then fixes the parse (green).

**One overfit run.** The full loop — model, loss, optimizer, collation — can
drive loss to ~0 on two samples. Catches sign errors, lr-schedule bugs, and dead
gradients in one test. Mark it slow; run it on the tiny random-weight model.

## Not worth writing — test theater

These look like coverage and catch nothing. Delete on sight:

```python
# THEATER: wiring restated. If the registry breaks, the first run throws
# KeyError with a clear message. This can only fail if someone edits the
# line it restates.
def test_registry_resolves_model_class():
    assert get_annotator_class("model-name") is ModelClassName

# THEATER: depends on ~/.cache contents; skips on CI, "passes" locally,
# verifies nothing anywhere.
def test_processor_loads_from_snapshot():
    snapshot = _cached_processor_snapshot()
    if snapshot is None:
        pytest.skip("no cached snapshot")
```

The shared pattern: the test can only fail loudly, immediately, and with an
obvious fix — which means the first real run already covers it. Same goes for:

- Constructor/config smoke tests (`build_config(...)` returns a config)
- Testing the language or framework (an ABC raises `TypeError`)
- Asserting a mock was called with the arguments you just passed
- Shape-only tests on your own code (`out.shape == (B, T, D)`) when a parity or
  invariant test would assert the _values_

**Test count is not a progress metric.** Five tests that pin invariants beat
fifty that restate the source. When inheriting a suite, deleting theater is as
valuable as adding coverage.

## Characteristics of a good test

- Asserts on values and invariants callers depend on, not shapes or wiring
- Uses the public interface; survives a full internal rewrite
- Runs on CPU with tiny tensors in milliseconds (see
  [mocking.md](mocking.md) for tiny-model substitution)
- Deterministic: seeds passed explicitly, no network, no cache-dir dependence
- Fails for exactly one reason, and that reason is a real bug
