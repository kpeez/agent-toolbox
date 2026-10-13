---
name: reducer
description: Shape event-driven state as a pure reducer with a replayable trace. Use when code reacts to a stream of events (hooks, queues, agent turns, UI actions), when state goes wrong under some order of events, or when someone asks why a flow reached a state.
user-invocable: false
---

# Reducer

A **reducer** is one pure function, `step(state, event) -> state` (or
`-> {state, outputs}` when the reducer decides which effects run). Every change
to the state goes through it. A **shell** around it does the I/O: it observes
the world, turns each observation into an **event**, applies `step`, stores the
result, and runs the outputs. Because `step` is pure, a list of events replays
to the same states every time: that replay is the **trace**, and the trace is
what you test, view, and explain.

Use it where state changes on many kinds of event, events interleave, or the
same question keeps coming back: "why is it in this state?" Straight-line code
and one-shot transforms gain nothing; leave them as they are.

## Shape the reducer

1. **Name the events.** One past-tense fact per thing the shell observes
   (`ToolStarted`, `TurnCompleted`, `AskToggled`). Each event carries every
   value the decision needs: the time, ids, results. The shell reads the clock,
   generates ids, and parses external payloads; `step` never does.
2. **Make the state one value.** Everything the decisions read lives in it.
   Values that only drive rendering, such as a ticking clock, can stay outside.
3. **Write `step` as a total function.** Pure: no clock, randomness, I/O, or
   mutation of its input. Total: an unknown id or an event out of order returns
   a sensible state, never a throw. Keep the limits, caps, and status rules in
   `step`, where the trace can show them.
4. **Return outputs for effects whose choice depends on state.** An output is a
   request ("send advice", "cancel job 7"), not proof the effect happened; its
   result comes back as a later event. When every effect is unconditional, the
   shell runs it and `step` returns only state.
5. **Store atomically.** One store, one update per event:
   `update(store, s => step(s, e))`. Several stores updated one by one lose
   writes when events overlap.

Done when every state change in the module goes through `step`, and the shell
holds no decision a test would need to reach.

## Test the laws

Write each **law** in plain language first: "once every started call ends,
nothing shows as running." Keep a law only when a realistic bug breaks it: a
missed branch, an out-of-order event, a dropped update. A law that restates one
line of code (a cap that is a single `.slice`) is a no-op test.

Check each kept law with generated event sequences: Hypothesis
`RuleBasedStateMachine` in Python, fast-check `fc.commands` in TypeScript, or a
small seeded generator where the project takes no dependencies. Generate
domain-valid interleavings, close them out (finish what started), then assert
the law on the final state. Watch each property go red on a deliberate bug
before trusting it. The `testing-code` skill owns the general rules; read its
[property-testing reference](../testing-code/references/property-testing.md).

## Record and view the trace

Keep one fixed event list from a real or realistic run. Fold it through `step`
into JSON lines, one per event:

```json
{"i": 0, "event": {...}, "before": {...}, "after": {...}, "outputs": [...]}
```

Check the file in, with a command that rewrites it and a check that fails when
it is stale. Because the real `step` writes the trace, the trace cannot drift
from the code in any language.

Open the file in [assets/flow-viewer.html](assets/flow-viewer.html) (a static
page; load the file or drop it on the page) to step through the events and see
which state paths each one changed.

## Explain a step

When asked why the flow reached a state, answer from the trace: name the step
index, the event, the paths that changed, and the branch of `step` that changed
them. When the question is about an order of events the trace does not hold,
add that order to a test or a scratch trace and replay it, rather than
reasoning about it unaided.

## Proofs

Property tests check laws on many inputs; a proof covers all of them. Proofs
pay off only for a few invariants that must never fail, such as budgets,
termination, or exactly-once delivery. Read
[references/proofs.md](references/proofs.md) before proposing one.
