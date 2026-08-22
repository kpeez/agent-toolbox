---
name: opencode-delegation
description: "Route work to the OpenCode delegate tools — explore, implement, review — and choose the model each delegation runs on. Use when dispatching to swe:opencode-explorer/implementer/reviewer, calling mcp__opencode__* directly, or when a delegation needs a stronger or cheaper model than the role default, or when usage limits force re-pinning a model."
user-invocable: false
---

# OpenCode delegation and model selection

Three fixed tools carry every OpenCode delegation: `explore` (read-only,
plan session mode), `implement` (write, build session mode), and `review`
(read-only plus execute for running tests). The read/write boundary is
chosen by the tool and cannot be changed by the caller.

Each tool's roles.json profile supplies default `model` and `effort` values.
Both are overridable per call:

```json
{"task": "...", "cwd": "/abs/worktree/root", "model": "<provider/model-id>", "effort": "high"}
```

- Omitted fields fall back to the role default; nothing else about the
  profile moves.
- An unknown model id fails the call loudly. Nothing is ever silently
  rerouted to another model.
- Passing either field on a continued session re-pins it from that turn on;
  omitting both leaves the live session exactly as it was.
- Valid effort values are model-dependent. When overriding `model`, pass an
  `effort` the new model actually offers, or drop the override and keep the
  role's pairing.

## Choosing a model per call

Defaults in roles.json already encode the cost policy: exploration is
high-volume and cache-bound, so it rides the cheapest suitable model;
implementation rides the strongest agentic coding model; review must run a
different family than implementation so the reviewer does not share its
prior. Override only when the defaults no longer fit:

- Usage capped, throttled, or unsubscribed on the default provider: pin any
  available id with equivalent shape (context window for sweeps, agentic
  coding strength for writes).
- Review after an implementation override: keep the reviewer on a different
  model family from whatever implemented the change.
- Throwaway or tightly scoped work: a cheaper model on explore or implement
  is fine; never cheap out the one review a run gets.

Read the current defaults from roles.json (`opencode` section per role) —
this skill intentionally does not copy them, so repinning a model is a
one-file edit that no prose can outlive.
