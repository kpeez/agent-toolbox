---
name: principle-test-behavior-not-implementation
description: "When you write, change, or keep a test, assert what the code's users can observe, so that the test fails when that behavior breaks and keeps passing when only the internals change."
disable-model-invocation: true
---

# Test behavior, not implementation

A test is a claim about what users of the code can observe through its
interface. That includes return values, errors, state they can read back, and
effects on outside systems. Private helpers, internal call order, and
intermediate data are implementation.

Judge each test against two imagined edits:

- **Break the behavior.** Use a wrong value, or a skipped or doubled effect.
  If the test still passes, it proves nothing. The usual causes are a loose
  assertion, an expected value computed by the code under test, and an
  assertion on data that the test built itself.
- **Change the internals.** Keep every observable result. If the test fails,
  it is pinned to the implementation.

Keep a test that catches the first edit and survives the second. Rewrite or
delete the rest.

- Drive the code through its public interface with a concrete input.
- Derive the expected value from the requirement, not from a run of the code.
- What an external service receives is behavior. A call to an internal helper
  is not.
- Pair "this never happens" with a case where it does happen.
- Assert the error type that callers branch on, not the message.
