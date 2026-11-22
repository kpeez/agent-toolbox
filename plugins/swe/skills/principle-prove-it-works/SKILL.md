---
name: principle-prove-it-works
description: "Before you claim that a task is done or a change works, check the real artifact through its real entry point and give a VERIFIED, NOT VERIFIED, or INCONCLUSIVE verdict."
disable-model-invocation: true
---

# Prove it works

Verify every output by checking the real thing directly. Run the feature
through its real entry point, read the actual value, and inspect the diff.
Proxies do not count. Examples are file mtimes, self-reports, cached output,
and "it compiles". When a check fails, suspect the observation method before
the system. When the project has a verification skill, use it to drive the
feature.

Script the check when you can. A deterministic script that reruns the
comparison beats a one-time look. Keep its output where the human can see it.
Commit it only when the trail must be auditable later, per the `log-decisions`
skill.

Give one verdict. VERIFIED means you saw the expected behavior on the real
surface. NOT VERIFIED means you saw wrong behavior, or the check failed.
INCONCLUSIVE means you could not reach the real surface, or the observation
cannot tell success from failure. Say what blocked it. INCONCLUSIVE is not a
pass. These three words judge a change. A reviewer's verdict on a pull request
uses PASS, PASS+NOTES, or FAIL, and a swarm worker's report uses PASS,
ISSUES, or BLOCKED.
