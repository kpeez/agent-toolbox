# Mocking in ML Code

Mock at **system boundaries** only:

- Model hubs and pretrained weights — never download in a unit test
- Experiment trackers (W&B, MLflow), LLM provider APIs, cluster schedulers,
  object stores
- Wall-clock time

Don't mock:

- Your own modules: datasets, transforms, losses, samplers, schedulers, model
  wrappers
- The framework (torch, numpy) — control randomness with explicit seeds and
  `torch.Generator`, not by patching `torch.randn`
- Anything cheap to run for real on CPU

## Substitute, don't mock

In ML the dominant boundary is **pretrained weights** — an 8B-parameter
download. The substitute is not a `MagicMock`; it's the same architecture at toy
scale:

```python
def tiny_model() -> VideoTransformer:
    return VideoTransformer(Config(layers=2, d_model=32, heads=2, vocab=128))
```

Real forward, real backward, millisecond runtime — every masking, dtype, and
gradient bug is still reachable. A mocked model verifies nothing because no
tensor math runs. Same move for the rest of the stack: a 4-frame synthetic video
instead of the real dataset, an in-memory list instead of the data loader, CPU
instead of CUDA. (These are the "local-substitutable" dependencies in the
architecture skill's vocabulary.)

Mocks are the last resort, for dependencies with no faithful local stand-in —
a paid API, a scheduler, a tracker.

## Design for testability

**Accept dependencies, don't create them.** A tracker constructed inside the
training loop forces patching; an injected one swaps for a no-op:

```python
# Testable: train(model, data, tracker) with tracker: Tracker injected
# Untestable: wandb.init() buried inside the loop
```

**Return results, don't only produce side effects.** A `train_epoch` that
returns metrics is assertable; one that only logs to the tracker is not.

**Prefer specific ports over generic fetchers.** One method per operation means
each test fake returns one shape, with no conditional logic inside the fake:

```python
# GOOD: each method independently fakeable
class ModelHub(Protocol):
    def get_processor(self, model_id: str) -> Processor: ...
    def get_weights(self, model_id: str) -> Path: ...

# BAD: faking requires re-implementing the hub's routing
class ModelHub(Protocol):
    def fetch(self, path: str, **kwargs) -> Any: ...
```

If a boundary is hard to fake, that's a design signal — fix the interface, don't
write a cleverer mock.
