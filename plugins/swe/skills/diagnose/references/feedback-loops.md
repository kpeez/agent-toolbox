# Feedback loops

Use this reference when the diagnosis needs a specialized or repeated signal.
Choose the smallest evidence source that distinguishes the leading hypotheses;
do not build a harness merely to follow a fixed ranking.

## Useful forms

- A failing test or example at the seam that reaches the bug.
- An HTTP or CLI invocation against a running system, compared with known-good
  output.
- A headless browser script that asserts the affected DOM, console, or network
  behavior.
- Replay of a captured request, payload, event log, or trace.
- A throwaway harness over the smallest real subset of the system, with only
  true external dependencies substituted.
- A property or fuzz loop for a wrong-output class with a real independent
  oracle.
- A bisection harness across commits, datasets, versions, or configurations.
- A differential loop comparing old and new behavior or two configurations.

## Make the signal useful

Iterate on the loop itself: cache setup, narrow the scope, assert the specific
symptom, pin time and randomness, isolate the filesystem, and freeze network
inputs when appropriate. A short deterministic loop is valuable; a long flaky
one needs either a higher reproduction rate or an explicit limitation.

For performance regressions, establish a baseline with a timing harness,
profiler, or query plan before changing code. For intermittent bugs, loop the
trigger, add targeted stress, or narrow the timing window. A unique prefix on
temporary debug logs can make cleanup auditable.
