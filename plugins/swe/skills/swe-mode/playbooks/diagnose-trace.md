# diagnose-trace

Applies when: diagnose a captured profiling artifact, such as a cpuprofile, trace, spindump, or heap snapshot, handed over after the fact.

You own the diagnosis from the artifact.

Unlike diagnose-runtime, the capture already exists. The artifact is a fixed dataset. Read it and do not re-run it. Keep tooling generic, such as a DevTools or trace parser for a cpuprofile or `.json.gz`, a text editor for a spindump, and heap tooling for a heap snapshot. The deliverable is a cited diagnosis, not a fix.

1-identify-format: Identify the format and load it with the right tool. Parse large artifacts in a subagent and keep the reduced finding in the main thread. (diagnose, guard-the-context-window)
2-make-it-queryable: Load the trace or heap snapshot into sqlite, one row per sample, frame, or node, before you read it. (build-the-lever)
3-narrow-to-cause: Query for the frames that hold the most time and walk the call tree to the hot path. For a leak, follow the retainer chain to a GC root. For a spindump, find the stuck or blocked thread and its wait reason.
4-attribute-to-source: Map the hot frame to file, symbol, and line through the artifact's own symbols. A frame with no source mapping is not yet a diagnosis, so resolve the symbols or say the artifact lacks them.
5-confirm-with-pair: With a paired capture, diff the before and after artifacts to confirm. Otherwise, label the finding the strongest hypothesis the artifact supports. (explain-the-number)
6-note-throughput: Write `throughput checkpoint: n/a, read-only forensics`.

Reply: the artifact and its format, the reduced finding, the source location, the artifact paths, and whether a paired capture confirmed it. No fix unless asked. Once the cause is known, hand back to fix-bug or improve-performance.
