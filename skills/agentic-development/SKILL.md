---
name: agentic-development
description: "Agent-Driven Development discipline. Use when implementing any feature, bugfix, or behavior change — requires writing runnable examples before implementation and verifying red-then-green cycle."
---

# Agent-Driven Development (ADD)

**Describe behavior, write examples that prove it, then implement until they pass.**

When this skill is active, you MUST:

1. Write spec docs (`PLAN.md` and `SPEC.md`) BEFORE writing source code
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

## RUN_LOG.md

Log results every time you run an example:

```
### <script_name>
**Status:** PASS | FAIL
**Date:** <date>
**Description:** <what this verifies>
**Result:** <observation>
```

## Running tests and lint

This skill ships `scripts/agent_pytest.py` and `scripts/agent_lint.py`. Invoke them directly from the skill's `scripts/` directory:

```bash
python <skill-scripts-path>/agent_pytest.py -- tests/
python <skill-scripts-path>/agent_lint.py
```

Each wrapper prints structured JSON and writes a full log to `.agent/pytest-last.log` or `.agent/lint-last.log`. Run targeted tests first; run the full suite only to verify final state.

## Verification

Example failures are spec failures -- fix them before marking done.

## Cross-references

- Use `/grill-me` to stress-test a plan before writing examples.
- Use `/spec new <name>` to scaffold a full spec with examples directory.
