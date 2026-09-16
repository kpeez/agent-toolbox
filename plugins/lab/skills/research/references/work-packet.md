# Lab work packet

Use this reference only when a research, deep-research, or autoresearch run is
part of a configured Linear workflow. Otherwise use the selected tracker route or keep the run local and do not
load it.

## Launcher

The Lab tracked workflow reaches the shared runtime through a thin launcher that
forwards public operation JSON to the entry point named by the
`SWE_WORKFLOW_ENTRYPOINT` environment variable and probes capabilities for
`interface_version=1`. The operator provisions that variable; do not hardcode or
link another plugin's path or private files. When the dependency is missing, the
launcher reports a useful error instead of pretending to run.

## Packet

A tracked research packet records, at minimum:

- the question and hypothesis;
- the stopping rule and the budget;
- the exact code revision and the environment or host;
- configuration, dataset, and seed values;
- the compute envelope and expected artifacts;
- an `experiment_run_id` distinct from any step or trial `run_id`.

For a memo without experiments, mark experiment-only fields not applicable with
a reason; do not invent compute, datasets, seeds, or job identifiers.

## Operations

Inspect existing permission before any apply. If the required `record` or
`publish` permission is missing, keep preparation local and use previews only.
A packet records provenance; it never authorizes a launch.

Record the run through `start`, `progress`, `handoff`, and `result` note kinds
via `record`, with the analysis and review each phase requires. Do not start a
duplicate because a prior response was missing; reconcile state first.
Operational handoff belongs in the private tracker packet or current-state
comment, not a second tracker.

In a handoff, identify each retained memo/report by its configured documentation
root and relative path, or a usable link. Include its revision or content hash,
knowledge date and relevance. Resolve relative work paths from the recorded
worktree and include newly created artifacts in the uncommitted-work observation.
Flag inaccessible essential output. A code check is research evidence only when
the research acceptance criteria require it; do not turn an unrelated code fix
into a research completion gate.

## Deferred

Run observation reporting is deferred. Do not describe it as delivered or build
an empty stub for it.

Resolve the Lab launcher from this installed reference as
`../../../scripts/workflow.py`, then pass the operation and ordinary CLI flags:
`--packet`, `--config`, `--state`, `--authority`, `--request`, and explicit `--apply`.
The default is preview. Missing `SWE_WORKFLOW_ENTRYPOINT` returns
`missing_dependency`; no sibling engine is imported or copied. `--help` works
without the dependency.

A `result` note must include `outcome: supported|negative`, no running jobs,
and `acceptance_evidence` covering the packet's criteria. Its `research` object
contains `question`, `config`, `dataset`, `seeds`, `run` (with
`experiment_run_id` and `code_revision`), `artifacts` (each URI, SHA256, configured `documentation_root` and relative `path`),
`analysis` (conclusion and limitations), and independent scientific `review`
(reviewer, approved decision and evidence). These are recorded observations;
the runtime checks declared local artifact bytes but does not perform scientific
interpretation or independently observe compute. URL-only artifact observation
remains pending and cannot prove Done. Required review and a separate audit
still inform delivery; nothing marks Done automatically.

The first slice never launches research jobs. Persistent run ownership,
independent observation, app notifications and inbound replies remain stage 2–3
milestones. Missing compute configuration blocks activation, not local packet work.
