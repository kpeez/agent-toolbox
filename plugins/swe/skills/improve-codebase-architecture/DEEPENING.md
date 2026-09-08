# Deepening

How to deepen a cluster of shallow modules safely, given its dependencies. Uses
the vocabulary in `SKILL.md` — **module**, **interface**, **implementation**,
**depth**, **seam**, **adapter**.

When you assess a candidate for deepening, classify each dependency it has. The
categories below are heuristics for how to test the deepened module across its
seam, not rules that override the behavior and constraints at hand.

## Dependency categories

### 1. In-process

Pure computation, in-memory state, no I/O — a loss function, an advantage
estimator, a tokenizer, a replay-buffer sampler, a reward shaper. These are often
good deepening candidates because they can be merged and tested through the new
interface directly. No adapter is usually needed.

### 2. Local-substitutable

Dependencies that have a faithful local stand-in: a 2×2 grid-world instead of the
real env, an in-memory dataset instead of the data loader, a CPU tensor instead
of CUDA, a 5-step fake trainer instead of a full run. Deepening is practical when
the stand-in faithfully represents the behavior at risk. Test the deepened
module with the stand-in running in the suite; an external port is unnecessary
when the seam remains internal.

### 3. Remote but owned (ports & adapters)

Your own services across a network boundary — a training service, a model server,
a feature store, an experiment DB. A **port** (interface) at the seam can keep
logic in the deep module while injecting transport as an **adapter**. When this
seam is justified, tests can use an in-memory adapter and production can use an
HTTP, gRPC, or queue adapter.

> _"Define a port at the seam, implement an HTTP adapter for production and an
> in-memory adapter for testing, so the logic sits in one deep module even though
> it's deployed across a network."_

### 4. True external (mock)

Third-party services you don't control — W&B, an OpenAI/Anthropic API, a Slurm/Ray
scheduler, an object store. An injected port with a mock adapter can isolate
logic that does not require the real service. Use representative integration or
contract evidence when the real boundary behavior is itself at risk.

## Seam discipline

- **Treat adapter count as evidence.** Multiple justified adapters make a seam
  concrete. A single adapter may still earn a port for a real external contract
  or faithful test substitute; otherwise it may be needless indirection.
- **Internal vs external seams.** A deep module can have internal seams (private
  to its implementation, used by its own tests) as well as the external seam at
  its interface. Don't expose internal seams through the interface just because
  tests use them.

## Testing strategy: replace, don't layer

- Remove old tests on shallow modules only after tests at the deepened module's
  interface preserve their useful, distinct coverage.
- Write new tests at the deepened module's interface. **The interface is the test
  surface.**
- Assert on observable outcomes through the interface, not internal state. A test
  that must change when the implementation changes is testing past the interface.
