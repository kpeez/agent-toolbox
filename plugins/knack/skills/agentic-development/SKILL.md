---
name: agentic-development
description: "Agent-Driven Development discipline. Use when implementing any feature, bugfix, or behavior change — requires writing runnable examples before implementation and verifying red-then-green cycle."
---

# Agent-Driven Development (ADD)

**Describe behavior, write examples that prove it, then implement until they pass.**

When this skill is active, you MUST:

1. Write the spec (`SPEC.md`: human goal/scope header + agent design body) BEFORE writing source code
2. Write runnable example scripts BEFORE implementation
3. Run examples to confirm they fail (red)
4. Implement the feature
5. Run examples to confirm they pass (green)

If you catch yourself implementing without examples that verify the behavior,
STOP. Write the examples first.

## Example script conventions

- Self-contained and runnable (e.g., `python examples/build_pipeline.py`)
- Exit 0 on success, non-zero on failure
- Print what they're checking and the result
- Written BEFORE implementation (they fail initially)
- Name scripts after the behavior they verify
- Avoid generic names like `basic_usage.py`, `example.py`, or `test.py`
- If a spec has one example, that filename should still describe the workflow or
  outcome it proves

## Run log

Log results every time you run an example. In the spec context this lives in the
`## Run Log` section of `specs/<feature>/STATUS.md`:

```
### <script_name>
**Status:** PASS | FAIL · **Date:** <date>
**Verifies:** <what this verifies> · **Result:** <observation>
```

## Running tests and lint

This skill ships `scripts/agent_pytest.py` and `scripts/agent_lint.py`. Invoke them directly from the skill's `scripts/` directory:

```bash
uv run <skill-scripts-path>/agent_pytest.py -- tests/
uv run <skill-scripts-path>/agent_lint.py
```

Each wrapper prints structured JSON and writes a full log to `.agent/pytest-last.log` or `.agent/lint-last.log`. Run targeted tests first; run the full suite only to verify final state.

## Verification

Example failures are spec failures -- fix them before marking done.

## Test quality

Examples prove end-to-end behavior; unit/integration tests prove finer-grained
behavior in the same red→green loop. Both obey one rule: **test behavior through
public interfaces, not implementation details.** Code can change entirely; tests
shouldn't.

**Good tests** read like a specification — "user can checkout with valid cart"
tells you what capability exists. They exercise real code paths through public
APIs and survive internal refactors.

**Bad tests ("mock-slop")** couple to internal structure. Delete or rewrite them
on sight. Red flags:

- Mocking your own classes/modules or internal collaborators
- Testing private methods, or asserting on call counts/order
- Verifying through a side channel (querying the DB directly) instead of the
  interface
- The test breaks when you refactor but behavior didn't change
- The test name describes HOW, not WHAT

**Mock only at system boundaries** — external APIs, time/randomness, sometimes
the database or filesystem. Never mock anything you control. If a boundary is
hard to mock, that's a design signal: inject the dependency and prefer specific
SDK-style functions (`getUser(id)`) over one generic fetcher.

**Vertical, never horizontal.** One test → one implementation → repeat. Do NOT
write all tests first then all code — bulk-written tests verify *imagined*
behavior and assert on shape (data structures, signatures) rather than what
callers care about. Each test should respond to what the previous cycle taught
you. Never refactor while red; get to green first.

You can't test everything. Confirm with the user which behaviors matter most and
concentrate effort on critical paths and complex logic, not every edge case.

## Subagent Execution

For multi-task plans, delegate to fresh subagents rather than implementing directly in the current session. Provide each subagent exactly the context it needs — no more. This preserves your coordination context and lets independent tasks run in parallel.

### Sequential or parallel?

- Tasks share files or have ordering dependencies → **sequential**
- Tasks are independent (disjoint files, no shared state) → **parallel**

When uncertain, sequential. Parallel conflicts are harder to recover from than sequential slowness.

### Model selection

Use the least powerful model sufficient for the task:

| Complexity | Signals                                                     | Claude       | Codex          |
| ---------- | ----------------------------------------------------------- | ------------ | -------------- |
| Low        | 1–2 files, mechanical change, complete spec                 | haiku        | gpt-5.4-mini   |
| Medium     | Multi-file, integration concerns, pattern matching          | sonnet       | gpt-5.5        |
| High       | Architecture, design judgment, broad codebase understanding | most capable | gpt-5.5 (high) |

### Implementer dispatch

Always tell the subagent to follow ADD: examples first, red, implement, green.

```
You are implementing a task as part of <feature>. Follow the agentic-development
discipline: write runnable examples that verify the required behavior, confirm they
fail (red), implement, confirm they pass (green).

Context:
- Project: <one-line description>
- Spec: <paste relevant SPEC.md sections>
- Key files: <paths>
- Scene: <where this task fits in the overall plan>

Task:
<full task text>

Report your status when done:
DONE — implemented and verified
DONE_WITH_CONCERNS — done, but: <concern>
NEEDS_CONTEXT — blocked on: <what's missing>
BLOCKED — cannot proceed: <reason>
```

Handle each status before proceeding:

- **DONE**: proceed to spec compliance review
- **DONE_WITH_CONCERNS**: read the concern — address it if it touches correctness or scope, otherwise proceed
- **NEEDS_CONTEXT**: provide the missing info and re-dispatch
- **BLOCKED**: diagnose before re-dispatching — wrong model, task too large, or the plan is wrong; change something

### Spec compliance review

Before code quality review, verify the work matches the spec. Use a read-only, low-cost model.

```
Review whether the implementation matches the spec. Read-only — do not flag style
or quality issues here.

Spec:
<paste relevant SPEC.md sections>

Diff or files:
<paste diff or list paths to inspect>

Report:
COMPLIANT — all spec requirements implemented, nothing out of scope added
NON_COMPLIANT — missing: <list> / extra (not in spec): <list>
```

If NON_COMPLIANT: implementer fixes the gaps, then re-review. Do not proceed to code quality review until COMPLIANT.

### Code quality review

Use the `patch-reviewer` agent. Pass it the diff. Fix any blocking issues and re-review before moving on. Non-blocking suggestions are at your discretion.

### After each task

Update `specs/<feature>/STATUS.md`: move completed items to Done, update Next and Phase.

## Cross-references

- Use `/grill-me` to stress-test a plan before writing examples.
- Use `/spec new <name>` to scaffold a full spec with examples directory.
