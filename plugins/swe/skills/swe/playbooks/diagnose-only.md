# diagnose-only

Applies when: explain a failure, crash, hang, leak, or captured trace; no fix requested.

1-state-exact-failure: State the exact failure mode and the surface where it was seen. (diagnose)
2-build-feedback-loop: Build the fastest loop that reproduces the failure, or record why none exists. (diagnose)
3-seed-from-history: When a regression is suspected, check recent changes to the failing area. (why)
4-rank-hypotheses: Rank falsifiable hypotheses and change one variable per probe until one survives. (diagnose, fix-root-causes)
5-label-confidence: Label the cause reproduced, inferred from the evidence, or unresolved. (diagnose)
6-remove-instrumentation: Remove task-owned instrumentation and harnesses. (diagnose)

Reply: the cause with its label, the evidence, and the limits. No production-source edits.
