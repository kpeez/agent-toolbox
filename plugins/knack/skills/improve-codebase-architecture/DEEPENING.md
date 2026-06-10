# Deepening

How to deepen a cluster of shallow modules safely, given its dependencies. Uses
the vocabulary in `SKILL.md` — **module**, **interface**, **implementation**,
**depth**, **seam**, **adapter**.

When you assess a candidate for deepening, classify each dependency it has. The
category determines how the deepened module is tested across its seam.

## Dependency categories

### 1. In-process

Pure computation, in-memory state, no I/O — a loss function, an advantage
estimator, a tokenizer, a replay-buffer sampler, a reward shaper. **Always
deepenable:** merge the modules and test through the new interface directly. No
adapter needed. Most ML logic bugs live here and are cheapest to pin down here.

### 2. Local-substitutable

Dependencies that have a faithful local stand-in: a 2×2 grid-world instead of the
real env, an in-memory dataset instead of the data loader, a CPU tensor instead
of CUDA, a 5-step fake trainer instead of a full run. Deepenable if the stand-in
exists. Test the deepened module with the stand-in running in the suite — the
seam is internal, no port at the external interface.

### 3. Remote but owned (ports & adapters)

Your own services across a network boundary — a training service, a model server,
a feature store, an experiment DB. Define a **port** (interface) at the seam. The
deep module owns the logic; the transport is injected as an **adapter**. Tests use
an in-memory adapter; production uses an HTTP/gRPC/queue adapter.

> _"Define a port at the seam, implement an HTTP adapter for production and an
> in-memory adapter for testing, so the logic sits in one deep module even though
> it's deployed across a network."_

### 4. True external (mock)

Third-party services you don't control — W&B, an OpenAI/Anthropic API, a Slurm/Ray
scheduler, an object store. The deepened module takes the dependency as an
injected port; tests provide a mock adapter. Never reach for the real thing in a
unit test.

## Seam discipline

- **One adapter = a hypothetical seam. Two adapters = a real one.** Don't
  introduce a port unless at least two adapters are justified (typically
  production + test). A single-adapter seam is just indirection.
- **Internal vs external seams.** A deep module can have internal seams (private
  to its implementation, used by its own tests) as well as the external seam at
  its interface. Don't expose internal seams through the interface just because
  tests use them.

## Testing strategy: replace, don't layer

- Old unit tests on the shallow modules become waste once tests at the deepened
  module's interface exist — **delete them**.
- Write new tests at the deepened module's interface. **The interface is the test
  surface.**
- Assert on observable outcomes through the interface, not internal state. A test
  that must change when the implementation changes is testing past the interface.
