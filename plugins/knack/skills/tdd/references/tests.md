# What to Test — and What Not To

The test for a test: **what silent bug does it catch?** A bug is _silent_ if the
pipeline runs to completion and produces wrong numbers, leaked data, or broken
invariants. A bug is _loud_ if the first real run throws a traceback that any
agent fixes in one step. Tests exist to catch silent bugs. Loud bugs are already
covered — by the interpreter, the import system, and the first smoke run.

## Worth writing

### Parity with a reference implementation

The optimized path must match the naive path you can read and trust. This is the
single highest-value test in numerical code — it catches off-by-one chunking,
masking, and broadcasting bugs that produce plausible-but-wrong numbers.

```python
def test_chunked_attention_matches_naive():
    q, k, v = (torch.randn(2, 8, 64, 32, generator=gen) for _ in range(3))
    naive = naive_attention(q, k, v)          # readable einsum, O(n^2) memory
    chunked = chunked_attention(q, k, v, chunk_size=16)
    torch.testing.assert_close(chunked, naive, rtol=1e-4, atol=1e-5)
```

### Invariants the math demands

Causality, permutation invariance, equivariance under augmentation, masking.
These break silently — the model still trains, just on leaked information.

```python
def test_future_frames_cannot_affect_past_logits():
    frames = torch.randn(1, 16, 3, 224, 224)
    past = model(frames).logits[:, :8]
    frames[:, 8:] = torch.randn_like(frames[:, 8:])  # perturb the future
    past_after = model(frames).logits[:, :8]
    torch.testing.assert_close(past, past_after)
```

```python
def test_padding_frames_do_not_change_output():
    out_short = model(frames[:, :12], frame_mask=mask(12))
    out_padded = model(frames, frame_mask=mask(12))  # 4 garbage frames masked out
    torch.testing.assert_close(out_short, out_padded)
```

### Gradient flow and parameter freezing

A frozen backbone that isn't frozen, or an adapter that never receives gradient,
trains for days before anyone notices.

```python
def test_lora_finetune_updates_only_adapter_weights():
    model(batch).loss.backward()
    for name, p in model.named_parameters():
        if "lora_" in name:
            assert p.grad is not None and p.grad.abs().sum() > 0, name
        else:
            assert p.grad is None, f"frozen param received grad: {name}"
```

### Data integrity

Split leakage and misalignment are the most expensive silent bugs in applied ML —
they inflate every downstream metric.

```python
def test_splits_share_no_subjects():
    train, val = make_splits(manifest, seed=0)
    assert {c.subject_id for c in train}.isdisjoint(c.subject_id for c in val)
```

```python
def test_sampled_timestamps_index_the_frames_they_claim(synthetic_video):
    # synthetic video where frame i is a solid image with pixel value i
    frames, timestamps_s = sample_frames(synthetic_video, fps=2.0)
    for frame, t in zip(frames, timestamps_s):
        assert frame.float().mean() == pytest.approx(frame_index_at(synthetic_video, t))
```

### Round-trips

Save/load must be exact; parsers must survive what models actually emit.

```python
def test_checkpoint_roundtrip_reproduces_outputs(tmp_path):
    before = model(batch)
    save_checkpoint(model, tmp_path / "ckpt")
    restored = load_checkpoint(tmp_path / "ckpt")
    torch.testing.assert_close(restored(batch), before)
```

```python
@pytest.mark.parametrize("raw", FIXTURE_DIR.glob("model_outputs/*.txt"))
def test_parser_handles_captured_model_output(raw):
    events = parse_annotation(raw.read_text())
    assert all(e.start_s <= e.end_s for e in events)
```

Fixtures are **captured real outputs** — including the malformed ones that broke
the parser in production. Every parser bugfix adds the offending output as a
fixture first (red), then fixes the parse (green).

### One overfit run

The full loop — model, loss, optimizer, data collation — can drive loss to ~0 on
two samples. Catches sign errors, lr-schedule bugs, and dead gradients in one
test. Mark it slow; run it on the tiny random-weight model.

## Not worth writing — test theater

These look like coverage and catch nothing. Delete on sight:

```python
# THEATER: wiring restated. If the registry breaks, the first run throws
# KeyError with a clear message. Asserting `cls is ModelClassName` can
# only fail if someone edits the line it restates.
def test_registry_resolves_model_class():
    assert get_annotator_class("model-name") is ModelClassName

# THEATER: testing Python's ABC machinery, not your code.
def test_annotator_requires_generate():
    with pytest.raises(TypeError, match="generate"):
        VideoAnnotator(config=_config())

# THEATER: depends on ~/.cache contents; skips on CI, "passes" locally,
# verifies nothing anywhere.
def test_processor_loads_from_snapshot():
    snapshot = _cached_processor_snapshot()
    if snapshot is None:
        pytest.skip("no cached snapshot")
```

The pattern behind all three: the test can only fail loudly, immediately, and
with an obvious fix — which means the first real run already covers it. Other
recurring offenders:

- Constructor/config smoke tests (`build_config(...)` returns a config)
- Asserting a mock was called with the arguments you just passed
- Shape-only tests on your own code (`out.shape == (B, T, D)`) when a parity or
  invariant test would assert the _values_
- Anything that `pytest.skip`s when weights, GPUs, or caches are absent

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
