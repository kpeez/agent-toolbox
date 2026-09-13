# Mutation audits

Read this reference when changed or high-risk core logic may have weak evidence,
such as parsers, calculations, authorization, normalization, branching business
rules, or state transitions. A mutation audit is not a routine release gate.

Scope the audit to the changed or high-risk files. Sample a few plausible faults:
inverted comparisons, off-by-one boundaries, omitted branches, swapped
arithmetic operators, removed normalization, or invalid state transitions. A
surviving mutant earns a stronger behavioral test only when it represents a
credible product bug. Record equivalent, impossible, or irrelevant mutants and
move on; do not optimize a score or add mutation CI for its own sake.

When useful, [cosmic-ray](https://cosmic-ray.readthedocs.io/) and
[mutmut](https://mutmut.readthedocs.io/) can scope an audit to changed files.
Manual mutation is also acceptable: make one or two plausible changes, confirm
the relevant sensor fails, then restore production. The information matters,
not the framework.
