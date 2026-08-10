# What to Test — and What Not To

The test for a test: **what silent bug does it catch?** A bug is _silent_ if the
pipeline runs to completion and produces wrong numbers, leaked data, or broken
invariants. A bug is _loud_ if the first real run throws a traceback that any
agent fixes in one step. Tests exist to catch silent bugs. Loud bugs are already
covered — by the interpreter, the import system, and the first smoke run.

## Goals are covered by evidence, not one test each

There is no quota. A stated goal needs **evidence that it works**, and evidence
comes in three forms — pick the one the goal's failure mode calls for:

1. **A committed test** — when the failure is silent. Wrong numbers, leaked
   data, a broken invariant: nothing throws, so only an assertion catches it.
   The earn-the-test bar above decides.
2. **A shared pipeline-level test** — when several goals are exercised by one
   end-to-end run. Those goals all cite that single test as their evidence.
   Don't clone it per goal; a duplicate that fails for the same reason as an
   existing test carries no new information.
3. **A reproducible demo in the PR** — when the failure is loud on the first
   real run. `/ship-pr` already requires a pasteable command with its observed
   output as verification; for a loud-failure goal, that record _is_ the
   evidence, and a committed test on top of it is theater.

So three goals can be covered by one pipeline test plus two demos, and that is a
complete job — not a gap to backfill. The suite's job is to make silent failure
impossible, not to mirror the goal list.

## Worth writing

Four categories earn committed tests in any codebase. The examples below are
drawn from ML, but the categories are the frame — translate them to your domain.

### Code boundaries

Where untrusted or external input becomes structured internal data: parsers,
deserializers, config and schema loaders, protocol and API edges. The boundary
is the one place input legality is decided, which concentrates all the input
risk there. Test valid _and_ invalid input; interior code then trusts its types
and needs no re-checks (and no tests of those re-checks).

Parsers are tested against **captured real inputs** — every parser bugfix adds
the offending payload as a fixture first (red), then fixes the parse (green).
In ML that means real model outputs, not hand-written strings you imagine the
model produces.

### Calculation correctness

Any computation with an independent oracle you can check against: a reference
implementation, a known-good result, a mathematical identity, or a round-trip.
This is the highest-value test in numerical code, because the failure is always
silent — plausible-but-wrong numbers.

**Parity with a reference implementation.** The optimized path must match the
naive path you can read and trust. Catches chunking, masking, and broadcasting
bugs.

```python
def test_chunked_attention_matches_naive():
    q, k, v = (torch.randn(2, 8, 64, 32, generator=gen) for _ in range(3))
    naive = naive_attention(q, k, v)          # readable einsum, O(n^2) memory
    chunked = chunked_attention(q, k, v, chunk_size=16)
    torch.testing.assert_close(chunked, naive, rtol=1e-4, atol=1e-5)
```

**Round-trips.** Encode/decode, serialize/parse, checkpoint save/load must
reproduce the original exactly. One round-trip property beats a pile of
per-field examples — but only when the transform is real work, not a dataclass
handed to a library serializer.

### Behavior invariants

Properties that must hold for every input, which break silently while everything
still appears to run. Assert the relation, not one sampled output.

**Invariants the math demands.** Causality, masking, permutation invariance,
equivariance. The model still trains — just on leaked information.

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

### One end-to-end pipeline test

A single test that drives the assembled system through its real path with real
collaborators — the shared evidence several goals cite at once. One is usually
enough; a second only earns its place if it covers a genuinely different path.

In ML that test is **one overfit run**: the full loop — model, loss, optimizer,
collation — driving loss to ~0 on two samples. Catches sign errors,
lr-schedule bugs, and dead gradients together. Mark it slow; run it on the tiny
random-weight model.

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

# THEATER: tests the arg-parsing library, not your code. A broken flag fails
# loudly on the first invocation. Fifty of these are one equivalence class in
# a coverage costume.
def test_cli_parses_batch_size_flag():
    assert parse_args(["--batch-size", "8"]).batch_size == 8

# THEATER: restates a validator that already raises loudly, one branch per
# test. If the rule is worth pinning, pin it once at the boundary with a real
# payload — not once per field.
def test_negative_epochs_rejected():
    with pytest.raises(ValueError):
        TrainConfig(epochs=-1)

# THEATER: trivial serialization. asdict() is the library's contract, not
# yours. Round-trips earn a test when the transform does real work.
def test_config_to_dict_has_keys():
    assert set(asdict(cfg)) == {"lr", "epochs", "batch_size"}
```

The shared pattern: the test can only fail loudly, immediately, and with an
obvious fix — which means the first real run already covers it. Same goes for:

- Constructor/config smoke tests (`build_config(...)` returns a config)
- Testing the language, framework, or a library (an ABC raises `TypeError`)
- Asserting a mock was called with the arguments you just passed
- Shape-only tests on your own code (`out.shape == (B, T, D)`) when a parity or
  invariant test would assert the _values_
- Deriving the expected value by re-implementing (or calling) the code under
  test — the test passes even if you delete the implementation
- A behavior already pinned by a lower-level or pipeline test; the duplicate
  fails for the same reason and tells you nothing new

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
