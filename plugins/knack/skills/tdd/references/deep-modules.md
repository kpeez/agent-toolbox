# Deep Modules

From "A Philosophy of Software Design":

**Deep module** = small interface + lots of implementation

```
┌─────────────────────┐
│   Small Interface   │  ← Few methods, simple params
├─────────────────────┤
│                     │
│                     │
│  Deep Implementation│  ← Complex logic hidden
│                     │
│                     │
└─────────────────────┘
```

**Shallow module** = large interface + little implementation (avoid)

```
┌─────────────────────────────────┐
│       Large Interface           │  ← Many methods, complex params
├─────────────────────────────────┤
│  Thin Implementation            │  ← Just passes through
└─────────────────────────────────┘
```

When designing interfaces, ask:

- Can I reduce the number of methods?
- Can I simplify the parameters?
- Can I hide more complexity inside? (frame sampling, tokenization, device
  placement, retry logic — callers shouldn't see any of it)

Deep modules are also the test surface: one small interface to test through,
with the implementation free to change underneath. For restructuring *existing*
shallow modules — dependency categories, seams, adapters — use
`/improve-codebase-architecture`; this note is for designing new interfaces
during TDD planning.
