# High-value behavior patterns

Read this reference when a concrete independent oracle or representative
workflow needs an example. The examples are drawn from ML, but the shapes apply
to any domain.

## Independent calculation oracle

Compare optimized behavior with a small readable reference that shares no
implementation:

```python
def test_chunked_attention_matches_naive():
    q, k, v = (torch.randn(2, 8, 64, 32, generator=gen) for _ in range(3))
    expected = naive_attention(q, k, v)
    actual = chunked_attention(q, k, v, chunk_size=16)
    torch.testing.assert_close(actual, expected, rtol=1e-4, atol=1e-5)
```

## Behavioral invariant

Assert a relation the domain demands rather than a sampled output. For example,
changing future frames must not change past logits. Gradient flow and freezing
can use the same shape: a frozen backbone must not receive gradients while an
adapter must receive them.

## Data integrity

Split leakage and misalignment can silently inflate downstream metrics. A
synthetic input with known positions can prove that sampled timestamps index the
frames they claim; a split test can prove subject sets are disjoint.

## Representative workflow

Drive the assembled system through its public entry point with real
collaborators. One workflow may protect several claims; add another only for a
genuinely different risk. In ML, one overfit run on two samples with a tiny
random-weight model can expose sign errors, schedule bugs, and dead gradients
across the full loop.
