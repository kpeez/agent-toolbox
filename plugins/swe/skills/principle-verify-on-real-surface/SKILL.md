---
name: principle-verify-on-real-surface
description: "Before you claim a change works: run it through its real entry point, observe the real result, and give a VERIFIED, NOT VERIFIED, or INCONCLUSIVE verdict."
user-invocable: false
---

# Verify on the real surface

A claim that a change works needs a direct observation of the real thing. A
proxy is not evidence: a passing unit test, a clean compile, an agent's
self-report, a file timestamp, or a cached or derived value.

1. Find the real entry point that a user or caller uses: the CLI command, the
   HTTP endpoint, the browser page, the job runner, or the public API.
2. Run the change through it with an input that exercises the changed
   behavior. Read the actual output, value, or state.
3. When you can, script the check so that one command runs it again. Keep the
   command and its output as evidence that a reviewer can rerun.
4. Give one verdict:
   - **VERIFIED**: you observed the expected behavior on the real surface.
   - **NOT VERIFIED**: you observed wrong behavior, or the check failed.
   - **INCONCLUSIVE**: you could not reach the real surface, or the
     observation cannot tell success from failure. Say what blocked it.

INCONCLUSIVE is not a pass. Report a negative verdict as plainly as a positive
one.
