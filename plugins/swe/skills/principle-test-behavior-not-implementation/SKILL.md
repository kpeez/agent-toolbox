---
name: principle-test-behavior-not-implementation
description: "When you write, change, or keep a test, call the code as its users do and assert the exact result they see."
disable-model-invocation: true
---

# Test behavior, not implementation

A test calls the code as its users do and asserts the exact result they see.
Rewrite or delete any test that would still pass if every imported function
returned `undefined` or a wrong value.

These shapes fail that check:

- A loose assertion or none, such as `toBeDefined`, `toBeTruthy`,
  `not.toThrow`, or `toBeGreaterThan(0)`.
- A call or absence check only, such as `toHaveBeenCalled`,
  `not.toHaveBeenCalled`, `toBeUndefined`, or `toEqual([])`.
- An expected value computed by the code under test, such as
  `expect(f(a)).toBe(f(a))`.
- A restated constant, config default, table row, or prompt string.
- Assertions on data that the test built, with no call to the subject.

To fix the test, call the subject in the test body with one concrete input and
assert the literal output or effect. For a mock, assert the payload it
received. For an absence, also assert the presence on another input. For a
constant, test the mechanism that reads it with one input instead of restating
the value.

Keep relation checks across table rows (a key in two tables, a parent that
exists) and `*.test-d.ts` type checks.
