# diagnose-runtime

Applies when: diagnose a live runtime symptom, such as a leak, an idle CPU spin, or a glitch, from instrumentation of the running process.

You own the diagnosis. Instrument the live process. Do not theorize from source.

The deliverable is a cited diagnosis, not a fix.

1-capture-live-signal: Capture a real artifact on the matching surface, with the project's verification skill when one exists. Take a CPU profile for a spin, a heap snapshot for a leak, and a trace for a visual glitch. (diagnose)
2-reduce-to-smoking-gun: Reduce the artifact to the hot-path function, the retainer chain to a GC root, or the loop that fires without input. Parse large artifacts in a subagent and keep the finding in the main thread. (guard-the-context-window)
3-prove-mechanism: Confirm the hypothesis cheaply before you believe it. Inject instrumentation into the running process, for example through its debugger protocol, or hotfix the live code without a reload. (fix-root-causes, prove-it-works)
4-map-to-source: Map the finding to the file, symbol, and line that allocates or schedules.
5-note-throughput: Write `throughput checkpoint: n/a, read-only forensics`.

Reply: the signal captured, the reduced finding, how you proved the mechanism, the source location, and artifact paths. No fix unless asked. Once the cause is known, hand back to fix-bug or improve-performance.
