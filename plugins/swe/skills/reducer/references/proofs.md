# Proofs for a reducer

Read this when a reducer invariant seems to need more than property tests.
Proofs are opt-in: propose one to the user with its cost, never add one by
default.

## What a proof gives

A proof checker (Lean, Coq, Bend's BendTT kernel, TLA+ with TLAPS) accepts a
law only when it holds for every input the types allow. Property tests sample
inputs; a proof leaves no gap. Two kinds of law look alike and are not:

- **Concrete law:** a fixed input evaluates to a fixed output. Checked by
  evaluation at compile time, it gives the same assurance as a unit test.
- **Universal law:** quantified over inputs, with stated preconditions
  ("for all `t, n, cap` with `t <= cap`, `tree_after(t, n, cap) <= cap`").
  Only these carry the extra guarantee.

Count the universal laws before calling a model "verified".

## What a proof does not give

- **The law can be the wrong law.** A proof of the wrong property is still a
  proof.
- **Only the model is covered.** The adapter between the host and the model,
  the shell, and any native code stay unproven. Liveness results assume the
  host delivers each awaited event.
- **Unstated behavior is unproven.** Usability and output quality sit outside
  every law.

## When it pays

Propose a proof only when all of these hold:

- the invariant is small, stable, and stated in plain language;
- a violation is expensive (budget overrun, lost or duplicated delivery, a run
  that never stops); and
- property tests have run and the residual risk still matters.

## How it couples to the host

The model is written in the proof language and compiled to a host-callable
artifact (Bend compiles to JavaScript with a `.d.ts` whose types are
`unknown`). A thin, schema-checked adapter then:

1. maps host ids to the model's ids, one to one;
2. encodes host events as model constructors and decodes outputs back;
3. is the only path the shell and the trace viewer use to call the model.

Rebuild the artifact in CI and fail when it differs from the checked-in copy.
For a host the compiler does not target (Python for Bend), either call the
compiled artifact through a sidecar process over JSON lines, or keep a host
port of the reducer and replay the same fixture events through both, failing
on any difference.
